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
