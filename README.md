# Backcaster
A tool to generate a Marcel projection from historical data.

## Dashboard
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=jeffreywevans_backcaster&metric=alert_status&token=359f97ac0af656a39d22c306e113642adcd2d968)](https://sonarcloud.io/summary/new_code?id=jeffreywevans_backcaster)
[![Bugs](https://sonarcloud.io/api/project_badges/measure?project=jeffreywevans_backcaster&metric=bugs&token=359f97ac0af656a39d22c306e113642adcd2d968)](https://sonarcloud.io/summary/new_code?id=jeffreywevans_backcaster)
[![Code Smells](https://sonarcloud.io/api/project_badges/measure?project=jeffreywevans_backcaster&metric=code_smells&token=359f97ac0af656a39d22c306e113642adcd2d968)](https://sonarcloud.io/summary/new_code?id=jeffreywevans_backcaster)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=jeffreywevans_backcaster&metric=coverage&token=359f97ac0af656a39d22c306e113642adcd2d968)](https://sonarcloud.io/summary/new_code?id=jeffreywevans_backcaster)
[![Duplicated Lines (%)](https://sonarcloud.io/api/project_badges/measure?project=jeffreywevans_backcaster&metric=duplicated_lines_density&token=359f97ac0af656a39d22c306e113642adcd2d968)](https://sonarcloud.io/summary/new_code?id=jeffreywevans_backcaster)
[![Lines of Code](https://sonarcloud.io/api/project_badges/measure?project=jeffreywevans_backcaster&metric=ncloc&token=359f97ac0af656a39d22c306e113642adcd2d968)](https://sonarcloud.io/summary/new_code?id=jeffreywevans_backcaster)
[![Reliability Rating](https://sonarcloud.io/api/project_badges/measure?project=jeffreywevans_backcaster&metric=reliability_rating&token=359f97ac0af656a39d22c306e113642adcd2d968)](https://sonarcloud.io/summary/new_code?id=jeffreywevans_backcaster)
[![Security Rating](https://sonarcloud.io/api/project_badges/measure?project=jeffreywevans_backcaster&metric=security_rating&token=359f97ac0af656a39d22c306e113642adcd2d968)](https://sonarcloud.io/summary/new_code?id=jeffreywevans_backcaster)
[![Technical Debt](https://sonarcloud.io/api/project_badges/measure?project=jeffreywevans_backcaster&metric=sqale_index&token=359f97ac0af656a39d22c306e113642adcd2d968)](https://sonarcloud.io/summary/new_code?id=jeffreywevans_backcaster)
[![Maintainability Rating](https://sonarcloud.io/api/project_badges/measure?project=jeffreywevans_backcaster&metric=sqale_rating&token=359f97ac0af656a39d22c306e113642adcd2d968)](https://sonarcloud.io/summary/new_code?id=jeffreywevans_backcaster)
[![Vulnerabilities](https://sonarcloud.io/api/project_badges/measure?project=jeffreywevans_backcaster&metric=vulnerabilities&token=359f97ac0af656a39d22c306e113642adcd2d968)](https://sonarcloud.io/summary/new_code?id=jeffreywevans_backcaster)


## Running tests

```bash
pytest
```

## SonarQube setup for test + coverage analysis

This repository is configured with `sonar-project.properties` for Python source, tests, and report ingestion.

### 1) Install development dependencies

```bash
uv sync --extra dev
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

### Troubleshooting lockfile issues

- If `uv.lock` **exists but is invalid**: regenerate it in a networked environment with `uv lock` and commit the regenerated file.
- If uv.lock **does not exist**: run uv sync --extra dev to install dependencies and generate the lockfile, then commit the resulting file.

### Recommended contributor workflow

1. Install deps for development immediately:

   ```bash
   uv sync --extra dev
   ```

2. Regenerate lockfile before opening/merging PRs (network required):

   ```bash
   uv lock
   ```

3. Commit the updated `uv.lock`.

## CI/CD baseline for reliable quality gates

The GitHub Actions workflows now enforce two core pipelines:

1. **CI (`.github/workflows/build.yml`)**
   - Runs tests on Python 3.12, 3.13, and 3.14.
   - Builds coverage + JUnit reports in a dedicated job.

2. **SonarCloud (`.github/workflows/sonarcloud.yml`)**
   - Re-generates `coverage.xml` and `pytest.xml` before scanning.
   - Ensures Sonar always has fresh report inputs instead of defaulting to 0% coverage.

Recommended next quality gates to enable in SonarCloud and branch protection:
- Coverage on new code threshold (e.g. >= 80%).
- No new critical/blocker issues.
- PR status checks required for CI + Sonar before merge.
