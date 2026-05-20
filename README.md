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
- Python **3.12, 3.13, or 3.14**
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

`uv.lock` pins transitive versions for reproducible environments.

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
sonar-scanner -Dsonar.projectVersion=$(grep -m 1 '^version =' pyproject.toml | cut -d'"' -f2)
```

Sonar consumes:
- `coverage.xml`
- `pytest.xml`

---

## Security and responsible use

Please review `SECURITY.md` for reporting guidance. Backcaster is an analytical utility and should be validated independently before use in production pipelines.
