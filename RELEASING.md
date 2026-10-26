# Releasing Backcaster

## Prepare 0.5.3

The package version is defined in `src/backcaster/__init__.py`; setuptools reads it
when building both distributions. After changing the version, run `uv lock` and
commit `uv.lock` if it changes. Release notes are in `CHANGELOG.md`.

From the repository root, with Python 3.13+ and the development dependencies installed:

```bash
uv sync --locked --extra dev --no-install-project
uv sync --locked --extra dev --no-build-isolation
xvfb-run -a uv run --locked --no-sync pytest --cov=src --cov-branch --cov-fail-under=100
uv run --locked --no-sync ruff check src tests
uv run --locked --no-sync ruff format --check src tests
uv run --locked --no-sync mypy
uv build --no-build-isolation
uv run --locked --no-sync python -m twine check --strict dist/*
```

On headless Linux, install Xvfb and xauth to run the GUI tests; on a graphical
desktop, omit `xvfb-run -a`. Python must include Tk support.

The source archive includes `uv.lock`, release/policy files, and the documentation
(including upstream attribution) so the documented source workflow is available.

Use a clean `dist/` directory for release builds so previous versions are not uploaded.
The Publish to PyPI workflow can be run manually on the release candidate branch
to build, check metadata, and smoke test the wheel without uploading to PyPI.

## Configure Trusted Publishing

On PyPI, configure the `backcaster` project's GitHub Trusted Publisher (or a pending
publisher if creating the project):

| Setting | Value |
| --- | --- |
| Owner | `jeffreywevans` |
| Repository | `backcaster` |
| Workflow filename | `workflow.yml` |
| Environment | `pypi` |

In the GitHub repository, create or review the `pypi` deployment environment and
its release-tag deployment policy. Add required reviewers if desired. Publishing
uses OpenID Connect with `id-token: write`; no PyPI API token is needed in the repository.
These GitHub and PyPI settings must be configured separately from the repository files.

## Publish

1. Merge the prepared changes into `main` and confirm CI passes, including Python
   3.13 and 3.14 and the 100% coverage gate.
2. Create a GitHub release named **0.5.3**, using tag **v0.5.3** at the validated
   commit on `main`. Use the 0.5.3 changelog entry as the release notes.
3. Publish the GitHub release as a stable release. This triggers `workflow.yml`;
   a draft does not trigger publication, and a prerelease does not upload to PyPI.
4. Review the build and the `pypi` deployment job; approve it if the environment
   requires approval. The workflow verifies the tag matches the package version,
   builds the source archive and wheel, checks metadata, and tests wheel installation.
5. After the upload succeeds, verify from a fresh environment:

   ```bash
   python -m pip install backcaster==0.5.3
   python -c 'from backcaster import __version__; assert __version__ == "0.5.3"'
   backcaster --help
   backcaster hitters --help
   backcaster pitchers --help
   ```

With local data installed, smoke test the new league commands for a covered
projection year (for example, 2026 requires 2023–2025):

```bash
backcaster hitters --year 2026 --format csv --out hitters_2026.csv
backcaster pitchers --year 2026 --format csv --out pitchers_2026.csv
```

Check that each file has one row per PlayerID and the requested projection Year.
CSV counts are rounded and IP uses baseball notation, not decimal innings.
Verify the expanded stat columns and the batter `BA` label. Check
batting rates and WHIP at three decimals, ERA at two, per-nine pitching rates
at one, and SO/W at two. W-L% is a three-decimal fraction. Undefined W-L% and
SO/W should be blank. Confirm the local CSVs include the fields listed in the
README before testing.

For 0.5.3, verify the desktop workspace on a graphical desktop:

- Launch `backcaster-gui` and `python -m backcaster.gui`; confirm the title and
  navigation show Backcaster v0.5.3.
- Load local Lahman selections and generate player, team, all-hitter, and
  all-pitcher reports. Verify player IDs distinguish duplicate names and the
  batting/pitching selector follows report scope.
- Export HTML and CSV into a selected folder, including a folder outside the
  working directory. Confirm exports include every player when the preview is
  capped at 500 rows. Verify save cancellation and overwrite confirmation.
- Set comparison to Yes and verify batting and pitching actuals and actual-minus-
  projected variances in the preview, HTML, and CSV. Set No and regenerate to verify
  projection-only output. Missing target-season data must show an error; partial
  player coverage must leave unavailable actuals and variances blank.
- Confirm numeric values are centered in the GUI and HTML, including actuals and
  variances, and HTML sort arrows do not shift the heading labels. Names and
  player IDs remain left-aligned. Regenerate older HTML exports to see the fix.
- Save both folder preferences and restart the app to confirm persistence.
- Confirm bad filters, missing data, and unwritable folders show readable errors.

For the batting calculations and 0.5.3 age/export changes, verify:

- Age 29 leaves independent event rates unchanged before raking. At age 25,
  beneficial events get a 1.024 multiplier and SO gets 0.976; at age 32 these are
  0.991 and 1.009. SH/SF stay neutral before raking, and OUT is the residual PA.
- Player PA, reliability, league event rates after raking, and IBB/GDP bounds
  remain conserved. Model rate precision is unchanged. Verify displayed and calculation ages use
  completed age on June 30 (June 30 birthday included, July 1 excluded), and
  missing/invalid birth dates are excluded with a readable warning.
- Verify birthdays on June 30 versus July 1, leap-day births, invalid dates, and
  incomplete dates. Player/team/batch projections and actuals must agree on age.
  Confirm People.csv includes birthYear, birthMonth, and birthDay; incomplete
  player dates are excluded with warnings, and missing columns give a data error.
- Verify batting exported TB equals H + 2B + 2×3B + 3×HR from displayed counts.
  BA/OBP/SLG/OPS and comparison variances use the rounded-count export basis;
  model DataFrames and pitching rate calculations remain full precision.
- Recreate older projections before comparing model versions. The reported
  reference MAE improvements are not independently reproduced; do not describe
  them as verified accuracy gains. See `docs/BATTER_MODEL.md`.

Also verify existing report behavior:

- Historical HTML comparisons work for both batters and pitchers with target-year
  results available. Projection inputs still use only the three preceding years.
  Actual and Variance rows start collapsed; Expand all and Collapse all control
  every player, and Reset restores collapsed rows. Rows stay with their player when sorting
  or filtering; print preserves the current view. Variance is actual minus
  projected, with signed baseball notation for IP. Missing target-year player
  records have a clear label and blank variances. CLI and CSV comparisons fail
  with a readable error before loading data.
- Nested export paths inside the current working directory succeed. Paths outside
  it, including parent traversal and symbolic-link escapes, return status 2
  before data loading or filesystem writes. Python writers default to the same
  boundary, accept an explicit `output_root`, and return resolved absolute paths.

- A one-out pitcher and an outless pitcher with a batter faced receive low-sample
  projections. Dated snapshots also work for pitchers, without changing retained
  forecasts. Confidence labels are not inclusion gates.

- A hitter with just three PA in the latest lookback season is included with
  low reliability and ConfidenceTier=low-sample; no PA or reliability gate applies.
- A dated eligibility snapshot filters players and team membership as of its
  stated date without changing retained players' projections. Both confidence
  tiers and EligibilityAsOf appear in exports.

- Pitcher IP follows `0.5 × last-year IP + 0.1 × two-years-ago IP + 60`; missing
  years contribute zero. A pitcher with only third-year history projects for 60 IP.

- Reliability shows six decimals in CLI, CSV, and HTML, and undefined batter
  BA/OBP/SLG/OPS display blank.
- `player --player-id <Lahman ID>` selects a duplicate-name player. Supplying
  both `--name` and `--player-id` fails with a usage error.
- `--out` with CLI format and unwritable file-output paths return status 2
  with a readable error and no traceback.
- Dangerous Name/PlayerID prefixes are escaped with an apostrophe in CSV.
- Python API callers use `DataLoadError` and the population batter API as
  described in the 0.4.2 changelog; projection numeric columns retain numeric dtypes.

Generate and open an HTML report as well:

```bash
backcaster hitters --year 2026 --format html --out hitters_2026.html
backcaster pitchers --year 2026 --format html --out pitchers_2026.html
# Historical comparisons require 2022–2025 in the local dataset:
backcaster hitters --year 2025 --format html --compare-actuals --out hitters_accuracy_2025.html
backcaster pitchers --year 2025 --format html --compare-actuals --out pitchers_accuracy_2025.html
```

Verify batting export TB equals rounded H + 2B + 2×3B + 3×HR, and batting rates
use those rounded components, including actuals and variance rows. Model
DataFrames must remain unchanged.

Verify Name/Year/Player ID/Age column order, rounded counts, fixed rate precision,
search, numeric sorting, reset, and print layout. Reports need no external assets.

PyPI versions are immutable. If an upload partially succeeds, investigate the
published files before retrying; do not replace an existing version's artifacts.
