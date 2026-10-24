# Backcaster

Backcaster is a Python CLI that produces **Marcel-style MLB projections** from the prior three seasons of data using local Lahman CSV files and `pandas`.

It supports:
- **Single player projections** (`player`)
- **Single team projections** (`team`)
- **League-wide projections** (`hitters`, `pitchers`, or `batch`)
- Output as terminal table, CSV, or HTML

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

To install a specific release, such as 0.3.6:

```powershell
python -m pip install --upgrade backcaster==0.3.6
```

Run the command using the same Python environment where you run Backcaster.
If you use a virtual environment, activate it first. Check the installed version with:

```powershell
python -m pip show backcaster
```

### Install from source (recommended for contributors)

```bash
# from repo root
uv sync
```

This installs runtime dependencies and the `backcaster` CLI entrypoint defined in `pyproject.toml`.

### Install in editable/dev mode

```bash
uv sync --extra dev
```

This adds test/lint/type-check/build tooling (`pytest`, `pytest-cov`, `ruff`, `mypy`, `pandas-stubs`, `build`).

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
- `player` requires `--name`
- `team` requires `--team`
- `batch`, `hitters`, and `pitchers` require no player or team option

```bash
backcaster <player|team|batch> [subcommand-options] --year <YEAR> --kind <batting|pitching> [--format cli|csv|html] [--out PATH]
backcaster <hitters|pitchers> --year <YEAR> [--data-dir PATH] [--format cli|csv|html] [--out PATH]
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

`--year 2026` projects 2026 from 2023–2025; it never reads 2026 statistics.
Both commands support `--data-dir`, `--format cli|csv|html`, and `--out`.
They are shortcuts for `batch --kind batting` and `batch --kind pitching`.
For a different data directory, add `--data-dir "C:\Baseball\lahman"`.
For HTML, use `--format html --out hitters_2026.html` (or a pitcher output filename).
File formats require `--out`; the CLI format prints to the terminal.

Players qualify for selection by meeting the existing PA/IP threshold in at least
one of those three seasons. This is a historical eligibility list, not an active
roster; pitchers who never reach the qualifying innings threshold (including most
relievers) remain excluded. Qualification selects players without removing their
other seasons from the calculation. Trades are combined into one player-season
before qualification, and all teams' statistics contribute once. The output is
one row per selected player, ready for comparison with reference projections.

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

Offline qualification uses a consistent modern rule across historical seasons:
at least **3.1 PA per game** for hitters and **one inning per game** for pitchers.
The season's game count is the maximum `G` in that year's `Teams.csv` records,
so shortened seasons have lower thresholds. The PA threshold is rounded to the
nearest integer (502 PA for 162 games, 186 PA for 60 games). This is an analytical filter, not a
reconstruction of historical award eligibility or batting-title exceptions.
Relievers generally do not qualify under this pitching rule.

Player stints are summed before qualification. Plate appearances are calculated
as `AB + BB + HBP + SF + SH`; missing/blank HBP, SF, and SH values count as zero.
Blank numeric counting-stat cells are also treated as zero; use a dataset with
complete records for the seasons you intend to project.
Pitching `IPouts` is divided by three for decimal innings, and `BFP` supplies
batters faced. Lahman player IDs keep different players with the same name separate;
ambiguous name lookups report the matching IDs.

Batter league regression and rebaselining use all non-pitcher player-seasons;
qualification selects the displayed players. Pitching retains its qualified-only
baseline, with real-age performance adjustments documented in
[the pitcher model](docs/PITCHER_MODEL.md). See [the batter model](docs/BATTER_MODEL.md) for the six-stage calculation,
real-age adjustment, PA formula, and explicit rebaselining choices.
Eligibility means qualifying in at least one of the three preceding seasons.
For every selected player, projections use all available seasons in that window,
including nonqualified seasons and seasons spent with other teams. For team selection, a traded player's full-season totals are assigned
to the team in their latest stint for that season; this is not a current-roster forecast.

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

> `--out` is required for `csv` and `html` formats.

---

## Output examples

### CLI table output (`--format cli`, default)

Example shape (columns vary by batting vs pitching):

```text
   PA    AB     H   2B   3B    HR    BB    SO   HBP    SF    AVG    OBP    SLG    OPS  Reliability          Name  Year
610.2 545.1 162.4 34.1  2.8  32.6  67.9 119.3   5.6   4.7  0.298  0.384  0.531  0.915        0.89  Mookie Betts  2026
```

### CSV output (`--format csv`)
A single-row CSV for `player`; multi-row CSV for `team`, `batch`, `hitters`, and `pitchers`.
Both populations include `PlayerID` for matching records across files.

### HTML output (`--format html`)
A basic HTML table (no custom CSS) suitable for quick sharing or embedding.

---

## Local data updates

Backcaster reads the local CSV files for each command and does not use the old
FanGraphs season cache. To refresh the data, replace the CSVs with a complete
Lahman distribution from the same edition. Existing online caches are ignored.

---

## Dependency notes

Runtime dependencies are intentionally minimal:
- `pandas` for tabular data processing and projection output
- `numpy` for numerical operations and rebaselining convergence checks

Development dependencies (`--extra dev`) include:
- `pytest`, `pytest-cov`
- `ruff`
- `mypy`, `pandas-stubs`

### Lockfile policy (`uv.lock`)

`uv.lock` pins transitive versions for reproducible environments when working from a Git checkout.

Release/source ZIP archives may not include `uv.lock`. If it is missing in your environment, regenerate it locally:

```bash
uv lock
```

Do not hand-edit `uv.lock`; regenerate it when dependencies change.

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
pytest --junitxml=pytest.xml --cov=src --cov-report=xml:coverage.xml
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
