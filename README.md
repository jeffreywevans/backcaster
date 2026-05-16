# backcaster
A tool to generate a Marcel projection from historical data.

## Running tests

```bash
pytest
```

## SonarQube setup for test + coverage analysis

This repository is configured with `sonar-project.properties` for Python source, tests, and report ingestion.

### 1) Install development dependencies

```bash
pip install -e '.[dev]'
```

### 2) Generate test and coverage reports

```bash
pytest --junitxml=pytest.xml --cov=src --cov-report=xml:coverage.xml
```

### 3) Run SonarScanner

```bash
sonar-scanner -Dsonar.projectVersion=$(grep -m 1 '^version =' pyproject.toml | cut -d'"' -f2)
```

SonarQube reads:
- coverage report from `coverage.xml`
- test execution report from `pytest.xml`

## Dependency locking with uv

### Why `uv.lock` exists

`uv.lock` is a generated lockfile that pins the full transitive dependency graph to exact versions for reproducible environments.

### How `uv.lock` is generated

From the repository root, run:

```bash
uv lock
```

`uv` reads dependency constraints from `pyproject.toml` and writes a lockfile that includes all direct and transitive dependencies. Do not hand-edit `uv.lock`.

### Why an invalid `uv.lock` was removed

A malformed or manually-authored lockfile can cause `uv` commands to fail (for example, parse/resolve errors), blocking setup for everyone.
Removing a broken lockfile is safer than keeping a known-invalid one in version control.

### What to do when you see "errors if it exists" vs "errors if it does not"

- If `uv.lock` **exists but is invalid**: regenerate it in a networked environment with `uv lock` and commit the regenerated file.
- If `uv.lock` **does not exist**: development can still proceed from `pyproject.toml` constraints (for example with `pip install -e '.[dev]'`). Then generate and commit `uv.lock` when network access is available.

### Recommended contributor workflow

1. Install deps for development immediately:

   ```bash
   pip install -e '.[dev]'
   ```

2. Regenerate lockfile before opening/merging PRs (network required):

   ```bash
   uv lock
   ```

3. Commit the updated `uv.lock`.
