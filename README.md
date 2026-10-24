# Backcaster

Backcaster is a Python CLI that produces **Marcel-style MLB projections** from the prior three seasons of data using [`pybaseball`](https://github.com/jldbc/pybaseball) and `pandas`.

It supports:
- **Single player projections** (`player`)
- **Single team projections** (`team`)
- **League-wide batch projections** (`batch`)
- Output as terminal table, CSV, or HTML

---

## Installation

### Requirements
- Python **3.13+**
- Internet access for first-time stat fetches (data is cached locally afterward)

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

All commands require:
- `--year` target projection year
- `--kind` one of `batting` or `pitching`

Subcommand-specific required options:
- `player` requires `--name`
- `team` requires `--team`
- `batch` requires no additional required option

```bash
backcaster <player|team|batch> [subcommand-options] --year <YEAR> --kind <batting|pitching> [--format cli|csv|html] [--out PATH]
```

### 1) Player projection

```bash
backcaster player --name "Mookie Betts" --year 2026 --kind batting
```

### Offline projections with Lahman CSVs

Extract your Lahman CSV distribution into a local directory. Pass `--data-dir`
to use it without any network requests, player-register downloads, or FanGraphs
cache reads. The directory must contain `People.csv`, `Teams.csv`, and
`Batting.csv` or `Pitching.csv` for the selected kind. Filenames are matched
without regard to case. The database is not bundled with Backcaster.

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
is unavailable. Without `--data-dir`, the existing pybaseball source is used;
FanGraphs may reject its automated requests with HTTP 403.

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

Only qualified player-seasons enter projections and league regression baselines.
Single-player projections require qualification in all three preceding seasons.
Team and batch projections use each player's available qualified seasons within
that window. For team selection, a traded player's full-season totals are assigned
to the team in their latest stint for that season; this is not a current-roster forecast.

### 2) Team projection

```bash
backcaster team --team LAD --year 2026 --kind pitching
```

### 3) Batch projection (all players returned by source data)

```bash
backcaster batch --year 2026 --kind batting
```

### File outputs

```bash
backcaster player --name "Mookie Betts" --year 2026 --kind batting --format csv --out ./out/mookie_2026.csv
backcaster team --team LAD --year 2026 --kind pitching --format html --out ./out/lad_pitching_2026.html
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
A single-row CSV for `player`; multi-row CSV for `team` and `batch`.

### HTML output (`--format html`)
A basic HTML table (no custom CSS) suitable for quick sharing or embedding.

---

## Cache behavior

Backcaster caches season stat pulls under:

```text
~/.cache/backcaster/
```

Cache details:
- Key pattern: `<kind>_<year>.parquet` (preferred) or `<kind>_<year>.csv` (fallback)
- Read order: Parquet first, then CSV
- Write behavior: atomic temp-file write + rename to reduce corruption risk
- Parquet write failures automatically fall back to CSV

Practical implications:
- First run for a season may be slower (network fetch).
- Re-runs are typically faster (local cache hit).
- If upstream data changes and you need a refresh, delete the relevant cache file(s) and rerun.

---

## Dependency notes

Runtime dependencies are intentionally minimal:
- `pandas` for tabular data processing and projection output
- `pybaseball` for MLB player/team seasonal stat retrieval and player ID lookup

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

## Security and responsible use

Please review `SECURITY.md` for reporting guidance. Backcaster is an analytical utility and should be validated independently before use in production pipelines.
