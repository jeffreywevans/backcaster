# Changelog

## Unreleased

- Project batter R, RBI, SB, CS, GDP, and IBB; derive TB and BA from full-precision hit components. Use the requested complete stat order and BA label.
- Expand pitcher counts to W/L/SV/R/IBB/HBP/BK/WP and derive W-L%, per-nine rates, and SO/W. Format WHIP to three decimals, per-nine rates to one, and SO/W to two.
- Share column-order constants across all exports, preserve identity metadata first, and document required CSV fields and formulas.

## 0.4.0

- Add standalone styled HTML reports with Name/Year/Player ID/Age first, summary cards, search, numeric sorting, sticky headers/names, and print/mobile layouts.
- Format counting stats as whole numbers, batting rates to three decimals, and ERA/WHIP to two decimals across terminal, CSV, and HTML outputs.
- Display IP in baseball outs notation, rounding to the nearest out, while preserving full-precision internal calculations.

Presentation/export change: CSV counting stats are now rounded and CSV IP uses
baseball notation (`161.1` = 161 innings plus one out), not decimal innings.
Batting rates have three decimal places; ERA and WHIP have two. Projection
DataFrames and calculations retain full precision. HTML is now a complete
standalone document with embedded CSS/JavaScript rather than a table fragment.
See [HTML reporting](docs/HTML_REPORTS.md). Projection formulas and eligibility
rules are unchanged in this release; Python 3.13+ remains required.

## 0.3.6

- Add `hitters` and `pitchers` shortcuts for pre-offseason league projections without team filters or `--kind`.
- Select players qualifying in at least one prior season, then retain all available history across teams and nonqualified seasons.
- Keep pitcher season weights attached to calendar years when a player has missing seasons, and export pitcher PlayerID for comparisons.
- Fix pitching team projections discarding seasons spent on other teams; verify traded players are combined before qualification and projected once.

Eligibility is qualification in at least one of the three prior seasons; all
available history contributes for selected players. This is a pre-offseason
projection population, not an active roster. Pitcher 5/4/3 weights and 200-IP
regression remain unchanged. Python 3.13+ is required.

## 0.3.5

- Apply birth-year-based pitcher aging to earned runs, hits, HR, walks, and strikeouts, recomputing ERA and WHIP without changing projected IP or BF.
- Require pitcher birth years and document the marcelR-derived equations and attribution. Pitcher season weights and regression constants are unchanged.

Pitcher commands now require valid `People.csv.birthYear` values. The previous
uniform age multiplier on pitcher innings is removed: aging changes performance
rates, not opportunities. Existing 5/4/3 pitcher weights, 200-IP regression, and
qualified-player baselines remain; see [pitcher aging](docs/PITCHER_MODEL.md).
Python 3.13+ remains required.

## 0.3.4

- Acknowledge Ben Dilday's marcelR as a methodological reference, document the
  inspected revision and implementation differences, and ship its MIT notice.
- Add the six-stage Tango batter pipeline: calendar-year weighting, player-specific non-pitcher league regression, projected PA, birth-year aging, and population rebaselining.
- Require Appearances.csv and People.csv birthYear for batter projections; keep qualified-player output selection and the existing pitcher formulas.
- Document explicit aging, primary-pitcher classification, and rebaselining choices and remaining differences from Baseball Reference.

Batter projections now require `Appearances.csv` and valid `People.csv.birthYear`
records in the local Lahman directory. Python 3.13+ remains required. Pitcher
formulas are unchanged, and exact Baseball Reference parity is not claimed.
See [the batter model](docs/BATTER_MODEL.md) for the calculation and validation.

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
