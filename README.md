# Backcaster

Backcaster is a Python CLI that produces **Marcel-style MLB projections** from the prior three seasons of data using local Lahman CSV files and `pandas`.

It supports:
- **Single player projections** (`player`)
- **Single team projections** (`team`)
- **League-wide projections** (`hitters`, `pitchers`, or `batch`)
- Output as terminal table, CSV, or HTML
- Historical comparisons against actual results in HTML reports (`--compare-actuals`)

---

## Installation

### Requirements
- Python **3.13+**
- An extracted Lahman CSV database covering the three prior seasons
- Internet access for package installation only; projections run offline

### Update an installed package

Upgrade to the latest release available on PyPI:

```powershell
python -m pip install --upgrade backcaster
```

To install a specific release, such as 0.4.3:

```powershell
python -m pip install --upgrade backcaster==0.4.3
```

Run the command using the same Python environment where you run Backcaster.
If you use a virtual environment, activate it first. Check the installed version with:

```powershell
python -m pip show backcaster
```

### Install from source (recommended for contributors)

```bash
# from repo root
uv sync --locked
```

This installs runtime dependencies and the `backcaster` CLI entrypoint defined in `pyproject.toml`.

### Install in editable/dev mode

```bash
uv sync --locked --extra dev
```

This adds test/lint/type-check/build tooling (`pytest`, `pytest-cov`, `ruff`, `mypy`, `pandas-stubs`, `build`, `setuptools`, `wheel`, `twine`).

### Build/install as a package

```bash
python -m build
pip install dist/backcaster-*.whl
```

---

## Quickstart CLI usage

All commands require `--year`, the target projection year.
The `player`, `team`, and `batch` commands also require `--kind batting|pitching`.
The `hitters` and `pitchers` commands choose their kind automatically.

Subcommand-specific required options:
- `player` requires exactly one of `--name` or `--player-id`
- `team` requires `--team`
- `batch`, `hitters`, and `pitchers` require no player or team option

```bash
backcaster <player|team|batch> [subcommand-options] --year <YEAR> --kind <batting|pitching> [--format cli|csv|html] [--compare-actuals] [--out PATH]
backcaster <hitters|pitchers> --year <YEAR> [--data-dir PATH] [--format cli|csv|html] [--compare-actuals] [--out PATH]
```

### Pre-offseason league projections

Once the latest regular season is present in your local Lahman files, generate
both populations without roster updates or team filters. For terminal output:

```powershell
backcaster hitters --year 2026
backcaster pitchers --year 2026
```

To save files for comparison with Baseball Reference:

```powershell
backcaster hitters --year 2026 --format csv --out hitters_2026.csv
backcaster pitchers --year 2026 --format csv --out pitchers_2026.csv
```

`--year 2026` projects 2026 from 2023–2025. It reads 2026 statistics only when
`--compare-actuals` is selected for a historical HTML report.
Both commands support `--data-dir`, `--format cli|csv|html`, and `--out`.
They are shortcuts for `batch --kind batting` and `batch --kind pitching`.
For a different data directory, add `--data-dir "C:\Baseball\lahman"`.
For HTML, use `--format html --out hitters_2026.html` (or a pitcher output filename).
File formats require `--out`; the CLI format prints to the terminal and rejects
`--out`. Invalid output options fail before data is loaded. Unwritable output
paths report an error on stderr and exit with status 2.

Exports must stay within the current working directory or its subdirectories.
Relative paths and absolute paths within that directory are accepted; paths that
escape it through `..` or symbolic links are rejected before data is loaded.
To export elsewhere, run Backcaster from the intended output directory.

Hitters receive a projection with any positive PA in the preceding three seasons,
subject to usable ages and the existing non-pitcher classification. There is no
minimum-PA or reliability gate. `ConfidenceTier` labels reliability at least 0.50
as `core` and lower values as `low-sample`; both tiers appear in every output.
Pitchers receive a projection with any recorded outs or batters faced in the
lookback window, including relievers and appearances without an out. They use
the same confidence labels, with no innings or reliability gate. All selected
players use their available three-year history.
Without a dated eligibility snapshot, this is a historical candidate population,
including potentially retired or otherwise unavailable players.

### 1) Player projection

```bash
backcaster player --name "Mookie Betts" --year 2026 --kind batting
```

### Offline projections with Lahman CSVs

All projections use local Lahman CSVs. On Windows, the default directory is
`C:\Baseball\lahman`; on other systems it is `~/Baseball/lahman`.
Set the `LAHMAN_DATA_DIR` environment variable to change the default, or pass
`--data-dir` to override it for one command. No network requests or online
fallbacks are made. The directory must contain `People.csv`, `Teams.csv`, and
`Batting.csv` or `Pitching.csv` for the selected kind. Both kinds require valid
`birthYear` values in `People.csv`; batters additionally require `Appearances.csv`. Filenames are matched
without regard to case. The database is not bundled with Backcaster.

For the default Windows directory, no additional flag is needed:

```powershell
backcaster player --name "Mookie Betts" --year 2024 --kind batting
```

See [Lahman database notes](docs/LAHMAN.md) for the supplied 1871–2025 edition's
coverage, attribution, license, and historical-data caveats, with its original README.

```powershell
backcaster player --name "Mookie Betts" --year 2022 --kind batting --data-dir "C:\Baseball\lahman"
backcaster team --team LAN --year 2022 --kind batting --data-dir "C:\Baseball\lahman"
backcaster batch --year 2022 --kind pitching --data-dir "C:\Baseball\lahman" --format csv --out pitchers.csv
```

Use Lahman's `teamID` values, such as `LAN` for the Dodgers (rather than the
FanGraphs abbreviation `LAD`). A projection year needs the preceding three seasons:
2022 requires 2019–2021. Missing seasons produce an error explaining which year
is unavailable. If the directory or required files are missing, the command
reports the missing file and directory; it never attempts an online fetch.

Batting inclusion requires positive lookback PA; pitching requires recorded outs
or batters faced. Neither has a minimum seasonal workload or reliability cutoff.
`season(..., qualified=True)` still exposes the historical PA/IP analytical filters
for Python callers; projection commands do not apply them.

Player stints are summed before projection. Plate appearances are calculated
as `AB + BB + HBP + SF + SH`; missing/blank HBP, SF, and SH values count as zero.
Blank numeric counting-stat cells are also treated as zero; use a dataset with
complete records for the seasons you intend to project.

Historical batting and pitching records with missing or invalid birth years are excluded with
a stderr warning identifying the count and sample player IDs. Remaining players
are still projected; no default age is substituted. An entirely unusable
population produces a clear error. See [historical data caveats](docs/LAHMAN.md).
Pitcher playing time is `0.5 × last-year IP + 0.1 × two-years-ago IP + 60`,
with missing calendar years contributing zero. The third prior season still
contributes to regression and reliability. See [the pitcher model](docs/PITCHER_MODEL.md).

Pitching `IPouts` is divided by three for decimal innings, and `BFP` supplies
batters faced. Lahman player IDs keep different players with the same name separate;
ambiguous name lookups report the matching IDs. Select one with `--player-id`
instead of `--name`, for example:

```bash
backcaster player --player-id bettsmo01 --year 2026 --kind batting
```

IDs match Lahman `People.csv.playerID` exactly and retain the same inclusion
rules as name lookups.

Batter league regression and rebaselining use all positive-PA non-pitcher
player-seasons. Output selection, including status snapshots, does not change
that calculation. Pitcher regression likewise uses the full historical sample
population, independently of roster, player, or team selection. See [the batter model](docs/BATTER_MODEL.md) and
[the pitcher model](docs/PITCHER_MODEL.md).

For every selected player, projections use all available seasons in the window,
including seasons spent with other teams. Without a status snapshot, team
selection uses historical last-stint membership for each season.

### Dated player eligibility

For a roster/status comparison, supply an explicit eligibility snapshot and date:

```bash
backcaster hitters --year 2025 --eligibility-file eligibility_2025.csv --as-of 2025-01-14 --format csv --out mlb_hitting_2025.csv
```

The CSV uses Lahman IDs and explicit inclusion decisions:

```csv
PlayerID,Year,AsOf,Eligible,Team
troutmi01,2025,2025-01-14,true,ANA
bettsmo01,2025,2025-01-14,true,LAN
```

Create these decisions from a roster/organization/free-agent/retirement source
as of the stated date. `Eligible` must be true or false. Unlisted players and
false rows are excluded; listed players still need a lookback sample (PA for
hitters, outs or batters faced for pitchers) and a usable birth year. Eligibility
never depends on reliability. The file can contain
multiple years and dates; only the exact `Year` and `AsOf` match is used, with
unique PlayerID values within that snapshot.

Both flags are required together and apply to batting and pitching. For pitchers,
use `backcaster pitchers` (or `--kind pitching`) with the same flags. Use separate
snapshot files if inclusion decisions differ between hitting and pitching roles.
`Team` is optional for league/player output and required for team output; it represents
membership at the snapshot date, with blanks allowed for unassigned players.
With a snapshot, team selection uses this membership rather than historical teams.
Exports include `EligibilityAsOf`. The snapshot filters output only; league
regression and rebaselining continue to use the full historical population.

For the January 14, 2025 Baseball Reference comparison, supply a snapshot actually
frozen to that date. Lahman history cannot reconstruct roster status on that date,
and later performance or final career dates are not used to guess it. Matching
504 benchmark rows requires the right status population as well as model inputs.

### 2) Team projection

```bash
backcaster team --team LAN --year 2026 --kind pitching
```

### 3) Batch projection (all eligible players)

```bash
backcaster batch --year 2026 --kind batting
```

### File outputs

```bash
backcaster player --name "Mookie Betts" --year 2026 --kind batting --format csv --out ./out/mookie_2026.csv
backcaster team --team LAN --year 2026 --kind pitching --format html --out ./out/lan_pitching_2026.html
```

> `--out` is required for `csv` and `html` formats and cannot be used with `cli`.

---

## Output examples

### CLI table output (`--format cli`, default)

Selected columns from a 2025 Mookie Betts projection (actual output includes
additional counting statistics, reliability, and age):

```text
        Name Year  PlayerID Age  PA  AB   H HR    BA   OBP   SLG   OPS
Mookie Betts 2025 bettsmo01  33 527 461 128 24 0.278 0.362 0.507 0.869
```

### Number formatting and baseball innings

Terminal, CSV, and HTML outputs use the same display rules:

- Counting statistics are rounded to the nearest whole number, with halves rounded
  up. Age and year are displayed as whole numbers too.
- BA, OBP, SLG, and OPS always show three decimal places, including `1.048` OPS.
  BA is the canonical batter output label (previously AVG).
  Rates with zero denominators remain undefined (NaN) and display blank;
  OPS is undefined when OBP or SLG is undefined.
- ERA shows two decimals; WHIP shows three. W-L% shows a three-decimal
  fraction, such as `0.524`. H9, HR9, BB9, and SO9 show one decimal; SO/W shows two.
  W-L% without any decisions and SO/W without walks are undefined and display blank.
- IP is rounded to the nearest out and displayed in baseball notation:
  `161.0` is 161 innings, `161.1` is 161 innings plus one out, and `161.2` is
  161 innings plus two outs. Three outs carry into the next whole inning.

Calculations and Python projection DataFrames retain full precision. Rates are
computed from unrounded totals, then formatted; they are not recalculated from
rounded displayed counts. Independently rounded totals may therefore not add up
exactly. Reliability shows six decimal places in CLI, CSV, and HTML output.

**CSV IP uses baseball notation too.** Convert `161.1` to `161 + 1/3` before doing
arithmetic; treating it as 161.1 decimal innings gives incorrect results. Internally,
Backcaster uses decimal innings (`IPouts / 3`), so ERA and WHIP calculations use
true innings rather than the displayed notation.

### Tracked statistics and order

All outputs put available Name, Year, Player ID, and Age metadata first, followed
by these statistics in order and then Reliability and ConfidenceTier; snapshot-filtered output appends EligibilityAsOf:

```text
Batters:  PA,AB,R,H,2B,3B,HR,RBI,SB,CS,BB,SO,BA,OBP,SLG,OPS,TB,GDP,HBP,SH,SF,IBB
Pitchers: W,L,W-L%,ERA,SV,IP,H,R,ER,HR,BB,IBB,SO,HBP,BK,WP,BF,WHIP,H9,HR9,BB9,SO9,SO/W
```

Lahman's batting `GIDP` is exported as `GDP`. The expanded counting-stat columns
must be present in the appropriate local CSVs; missing columns produce an error.
TB is derived as `H + 2B + 2×3B + 3×HR`; stolen bases do not add total bases.
BA is H/AB, SLG is TB/AB, OBP is `(H+BB+HBP)/(AB+BB+HBP+SF)`, and OPS is OBP+SLG.
IBB is already part of BB and is never added again to OBP or PA. Runs, RBI, SB,
CS, and GDP are contextual counts rather than additional PA outcomes.

Pitcher per-nine rates use unrounded counts and decimal IP: `9 × count / IP`.
SO/W is SO/BB; W-L% is W/(W+L). Runs allowed (`R`) and earned runs (`ER`) are
separate projections; ERA uses ER, while WHIP uses H+BB without adding IBB again.

### CSV output (`--format csv`)
A single-row CSV for `player`; multi-row CSV for `team`, `batch`, `hitters`, and `pitchers`.
Both populations include `PlayerID` for matching records across files.

### HTML output (`--format html`)
A standalone report with embedded CSS and JavaScript, ready to open in a browser
or share as one file. No server, CDN, fonts, or internet connection are required.

```powershell
backcaster hitters --year 2025 --format html --out hitters_2025.html
backcaster pitchers --year 2025 --format html --out pitchers_2025.html
backcaster hitters --year 2025 --format html --compare-actuals --out hitters_accuracy_2025.html
```

The first four columns are **Name, Year, Player ID, Age**, followed by counting
statistics and batting/pitching rates in a consistent order. The report includes:

- A player-count, projection-year, and projection-type summary.
- Search across player names, IDs, and statistics.
- Sortable column headings, with numeric sorting for statistics.
- Optional historical accuracy rows with a per-player expand/collapse control.
- A sticky name column/header and horizontal scrolling on narrow screens.
- A reset control and print layout for browser printing or saving as PDF.

Your display precision rules apply, including baseball innings notation. Rates
retain their trailing decimal places and OPS values above 1.000 display normally.
Search filters the visible rows; printing respects that current view. Without
JavaScript, the complete table is still readable. See
[HTML report customization](docs/HTML_REPORTS.md) for theme and column constants.

### Compare projections with actual results (new in 0.4.3)

Add `--compare-actuals` to a historical HTML report for either batters or pitchers:

```powershell
backcaster hitters --year 2025 --format html --compare-actuals --out hitters_accuracy_2025.html
backcaster pitchers --year 2025 --format html --compare-actuals --out pitchers_accuracy_2025.html
```

For these examples, the local Lahman files must cover **2022–2024** for the
projection and **2025** for the actual results, including target-year game counts
in `Teams.csv`. Use `--data-dir` to select the dataset. The 1871–2025 edition can
support a 2025 comparison; it cannot provide actual results for 2026.
The option also works with `player`, `team`, and `batch`; it requires
`--format html` and `--out` and is rejected for terminal or CSV output.

Projection calculations use only the three preceding seasons. Target-season
results are loaded afterward and matched by Lahman PlayerID, combining trade
stints without requiring the player to meet a seasonal qualification threshold.
Each projected player has two additional rows:

- **Actual** shows the player's recorded target-season results.
- **Variance** shows `actual - projected`, calculated before display rounding.
  For example, 25 actual HR against 20 projected HR displays `+5`.

Positive differences are green and negative differences are red. These colors
indicate direction: a positive ERA variance means more earned runs per nine
innings than projected. IP differences use signed baseball innings notation;
`+1.2` means one inning and two outs.

Rows start expanded. Use the control beside each player name to collapse or
expand them; the rows stay with their player when sorting or filtering, and
printing preserves the current view. A projected player without a target-season
record is labeled `Actual (no recorded stats)` and has blank variance cells.
Players absent from the projection population are not added from the actuals.
ConfidenceTier and Reliability describe the projection, not the actual results.

---

## Local data updates

Backcaster reads the local CSV files for each command and does not use the old
FanGraphs season cache. To refresh the data, replace the CSVs with a complete
Lahman distribution from the same edition. Existing online caches are ignored.

---

### Python data-loading errors

Local data-loading and validation failures raise
`backcaster.data.DataLoadError` (renamed from `DataFetchError`). Player lookup
failures continue to raise `PlayerLookupError`. The CLI reports these failures
and filesystem errors on stderr with exit status 2.

## Dependency notes

Runtime dependencies are intentionally minimal:
- `pandas` for tabular data processing and projection output
- `numpy` for numerical operations and rebaselining convergence checks

Development dependencies (`--extra dev`) include:
- `pytest`, `pytest-cov`
- `ruff`
- `mypy`, `pandas-stubs`

### Lockfile policy (`uv.lock`)

`uv.lock` is committed and pins runtime, development, and build dependencies. CI
installs uv 0.12.23 with a SHA-pinned `astral-sh/setup-uv` action, whose embedded
checksums verify the downloaded uv archive. CI uses
`uv sync --locked --extra dev` and fails if the lockfile is out of date. CI first
installs the locked tools with `--no-install-project`, then installs Backcaster
with `--no-build-isolation` to keep build dependencies pinned. CI builds
without build isolation using the locked build tools; wheel smoke tests install
hash-checked runtime dependencies exported from the same lockfile.

Release/source ZIP archives may not include `uv.lock`. If it is missing in your environment, regenerate it locally:

```bash
uv lock
```

Do not hand-edit `uv.lock`; run `uv lock` and commit the updated lockfile when
dependencies change. To deliberately refresh all pins, run `uv lock --upgrade`.

---

## What this projection does and does not claim

### What it does
- Implements a **Marcel-style** weighted/regressed projection over prior seasons.
- Uses configurable reliability/regression/playing-time assumptions in code defaults.
- Produces transparent, table-based outputs for downstream analysis.

### What it does **not** claim
- It is **not** an official MLB/club forecasting system.
- It does **not** model injuries, role changes, park effects, coaching strategy, or transaction context in a comprehensive way.
- It does **not** guarantee predictive superiority versus commercial/public projection systems.
- It should be treated as a **baseline projection tool**, not a betting or financial decision engine.

---

## Development and quality checks

For release preparation and PyPI Trusted Publishing, see [RELEASING.md](RELEASING.md).
Changes for the next release are recorded in [CHANGELOG.md](CHANGELOG.md).

### Run tests

```bash
pytest
```

### Coverage + JUnit reports

```bash
pytest --junitxml=pytest.xml --cov=src --cov-branch --cov-report=xml:coverage.xml --cov-fail-under=100
```

### Lint and types

```bash
ruff check .
mypy
```

### SonarScanner

```bash
sonar-scanner -Dsonar.projectVersion=$(PYTHONPATH=src python -c "from backcaster import __version__; print(__version__)")
```

Sonar consumes:
- `coverage.xml`
- `pytest.xml`

---

## Acknowledgments

Thank you to **Tom Tango** for developing and publishing the Marcel system, and
to **Ben Dilday** for [marcelR](https://github.com/bdilday/marcelR), whose open R
implementation provides a valuable methodological reference for our Python work.
We document the reviewed formulas, source revision, and implementation differences
in [our reference notes](docs/MARCELR_REFERENCE.md). The complete marcelR MIT
notice is preserved in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and shipped
with our distributions.

Thanks also to SABR, Sean Lahman, and the database contributors. See
[Lahman attribution and licensing](docs/LAHMAN.md). These acknowledgments do not
imply endorsement or exact agreement with another implementation's projections.

## Security and responsible use

Please review `SECURITY.md` for reporting guidance. Backcaster is an analytical utility and should be validated independently before use in production pipelines.

## Desktop GUI

Launch the desktop report workspace after installing Backcaster:

```bash
backcaster-gui
# Or, from a source checkout:
python -m backcaster.gui
```

The ServiceNow-inspired workspace displays **Backcaster** and the installed version,
with a dark green navigation rail, report filters, and a scrollable results table.
It requires a graphical desktop and Python's Tk support (on Debian/Ubuntu, install
`python3-tk`; official Windows/macOS Python installers normally include Tk).

1. Browse to the extracted Lahman CSV folder and click **Load selections**.
2. Select a projection season, then **Particular player**, **Team**, **All hitters**,
   or **All pitchers**. Player and team reports allow batting or pitching statistics.
   Player selections include Lahman IDs to distinguish duplicate names. You can also
   enter a full player name, an exact player ID, a team ID, or a season directly.
3. Select a report output folder. **Save folders** stores both folder preferences
   across launches; browsing also saves them. Settings are stored under the user's
   platform configuration directory in `backcaster/settings.json`.
4. Click **Generate report** to preview results, then **Export HTML** or **Export CSV**.
   The save dialog lets you choose a filename and confirms overwrites. Keep exports
   inside the selected report output folder, or change that folder first.

Projection and export work runs in the background. The table previews up to 500
players; exports contain the complete generated result. Exports always use the last
successfully generated report; click **Generate report** after changing filters.
The season list includes years with three preceding seasons in the loaded data.
Player and team lists include historical entries; the projection engine checks
eligibility for the chosen season. The existing CLI remains available with its
working-directory export restriction.

GUI integration tests use real Tk widgets. On a Linux machine without a display,
install Xvfb and xauth, then run `xvfb-run -a pytest`. CI runs the full suite and
coverage reports this way. Without a display, local runs skip window integration
tests; settings, export, and CLI tests still run normally.
