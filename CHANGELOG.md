# Changelog

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
