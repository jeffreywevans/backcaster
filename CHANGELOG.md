# Changelog

## 0.4.2

- Add an explicit `age` fallback to `project_team`, matching `project_player`; birth years take precedence and CLI projections still require them.

- Use recency-based pitcher playing time: `0.5 × last-year IP + 0.1 × two-years-ago IP + 60`. Missing years contribute zero; third-year history still informs regression and reliability. Apply the same formula to player, team, and batch projections.

- Prevent CSV formula injection by escaping Name and PlayerID cells beginning with `=`, `+`, `-`, `@`, tab, or carriage return.
- Add `player --player-id` to disambiguate duplicate names while retaining qualification rules. Require exactly one of `--name` or `--player-id`.
- Report unwritable output paths as CLI errors with exit status 2; reject `--out` with CLI output and validate output options before loading data.
- Preserve undefined batter rates as NaN and display them blank. Format Reliability to six decimals across CLI, CSV, and HTML; bind each numeric column's display precision correctly.
- Preserve numeric projection dtypes and vectorize pitcher population calculations, retaining the single-player formulas and shared league baseline.
- Read only needed Lahman CSV columns and reuse an indexed People lookup across seasons.
- Remove the unused legacy batting projection path and its misleading configuration fields. Document the population batter API and scope MarcelConfig to pitching.
- Rename the local data-loading exception to DataLoadError and document the Python API changes.
- Add uv.lock for reproducible CI, build tools, and wheel smoke tests; raise the pandas minimum to 2.2.2 for NumPy 2 compatibility and configure Dependabot for uv.
- Correct action-pin version comments, pass SonarCloud shell inputs through environment variables, and resolve static-analysis findings in exception tests.

Projection change: pitcher IP and counting-stat totals now follow the recency-based
playing-time estimate instead of a weighted seasonal average. Regressed per-IP
rates, aging, and reliability formulas remain unchanged.

Compatibility: `project_player` and `project_team` now support pitching only;
Python batting callers must use `backcaster.batters.project_batters` with the full
non-pitcher population. MarcelConfig no longer accepts `regression_pa`,
`default_pa_growth`, or `age_adjustment_fn`. Import `DataLoadError` instead of
`DataFetchError`. Undefined batter BA/OBP/SLG/OPS remain NaN internally and export
as blank cells; Reliability exports use six decimal places. CSV identity values
with dangerous prefixes receive a leading apostrophe. Python 3.13+ remains required.

## 0.4.1

- Project batter R, RBI, SB, CS, GDP, and IBB; derive TB and BA from full-precision hit components. Use the requested complete stat order and BA label.
- Expand pitcher counts to W/L/SV/R/IBB/HBP/BK/WP and derive W-L%, per-nine rates, and SO/W. Format WHIP to three decimals, per-nine rates to one, and SO/W to two.
- Share column-order constants across all exports, preserve identity metadata first, and document required CSV fields and formulas.

Export compatibility: batter exports now label batting average `BA` instead of
`AVG` and include the expanded stat columns in the documented order. WHIP now
has three decimal places. Local Lahman batting files must include R, RBI, SB,
CS, IBB, and GIDP; pitching files must include W, L, SV, R, IBB, HBP, BK, and WP.
Rates are calculated from unrounded projections; IBB remains part of BB and is
not counted again in PA or OBP. Python 3.13+ remains required.

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
