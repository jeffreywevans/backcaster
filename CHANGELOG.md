# Changelog

## Unreleased

- Add the six-stage Tango batter pipeline: calendar-year weighting, player-specific non-pitcher league regression, projected PA, birth-year aging, and population rebaselining.
- Require Appearances.csv and People.csv birthYear for batter projections; keep qualified-player output selection and the existing pitcher formulas.
- Document explicit aging, primary-pitcher classification, and rebaselining choices and remaining differences from Baseball Reference.

## 0.3.3

- Correct regression to use weighted evidence totals and derive reliability from
  the observed-evidence fraction; document the math audit and remaining model differences.
- Use local Lahman CSVs for all projections; remove online FanGraphs retrieval, player-register downloads, and the pybaseball dependency.
- Default to `C:\Baseball\lahman` on Windows or `~/Baseball/lahman` elsewhere, with `LAHMAN_DATA_DIR` and `--data-dir` overrides.

This release requires local Lahman data. Baseball Reference is the validation target,
but playing-time, age, and pitching-model differences remain; see
[the projection math audit](docs/PROJECTION_MATH.md). The obsolete
`MarcelConfig.reliability_scale` setting has been removed. Python 3.13+ is required.

## 0.3.2

- Document pip upgrades, installing a specific release, and checking the installed version.
- Add Lahman 1871–2025 database setup, coverage, attribution, licensing, and historical-data notes, with the supplied source README.
- Clarify that Lahman NULLs represent unknown values, while Backcaster currently treats blank numeric counts as zero.

This release updates documentation; projection behavior and Python 3.13+ requirements are unchanged.

## 0.3.1

- Add offline Lahman CSV projections through `--data-dir` for player, team, and
  batch commands, with qualified-player filtering, season-length thresholds,
  combined trade stints, and Lahman player identities.
- Simplify season loading and split composite test assertions to resolve Sonar findings.

Use `--data-dir "C:\Baseball\lahman"` to project from extracted local CSVs
without FanGraphs requests. Requires Python 3.13+ and data for the three prior
seasons. Qualification and team-selection rules are documented in README.md.

## 0.3.0

- Refactor CLI, player lookup, data, and projection exception tests so each assertion
  exercises one potentially failing call.
- Refactor the CLI entrypoint warning test to isolate the warning-producing call
  while retaining the exit assertion.
- Validate release tags, distribution metadata, and the installed wheel before
  publishing to PyPI. Manual workflow runs validate without publishing.
- Update package license metadata and add project links for PyPI.

This release retains the existing projection behavior and Python 3.13+ requirement.
