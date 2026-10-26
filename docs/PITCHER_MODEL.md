# Pitcher projection model

Pitcher projections now use completed age on **June 30** of the projection year for player,
team, and batch commands. The Lahman adapter excludes pitchers with missing,
incomplete, invalid, or implausible birth dates (June-30 ages outside 15–70), and logs
the excluded count and up to ten player IDs to stderr. Excluded pitchers do not
contribute to selection or league baselines. Remaining pitchers are projected;
if none have usable ages, the command returns a clear error. The birthYear, birthMonth, and birthDay
columns are required, and age 29 is never silently substituted by the CLI.

The low-level Python
`project_player` and `project_team` functions accept an explicit `age` fallback
for callers without a birthYear column; both default to 29. For team projections,
this fallback applies to every pitcher. The supplied fallback is interpreted as June-30 age. When birthYear is present,
a valid birthMonth and birthDay are also required; invalid or incomplete birth
dates raise an error rather than using the fallback. June 30 birthdays count as
reached, while July 1 birthdays reduce age by one relative to year subtraction.

The aging equations and direction choices are adapted from Ben Dilday's marcelR,
revision `13a1c7943f5a7317c9c812a28e299c2184060046`, `R/utilities.R` and
`inst/scripts/marcel_data_exporter.R`. Copyright (c) 2017 Ben Dilday, MIT.
See [the complete notice](../THIRD_PARTY_NOTICES.md) and
[adaptation notes](MARCELR_REFERENCE.md).

For age `a`, define a beneficial-performance factor:

- Above 29: `1 / (1 + .003 * (a - 29))`.
- At or below 29: `1 + .006 * (29 - a)`.

After regression, multiply SO by this factor. Divide ER, H, HR, BB, R, IBB, HBP, BK, and WP by it,
then recompute ERA and WHIP. At 29 the factor is 1. Age 34 means 1.5% more earned
runs/hits/walks/HR and SO divided by 1.015. At 25, SO increases 2.4% and the harmful
counts are divided by 1.024. Age adjustments do not change reliability, projected
IP, or BF. BF is retained as the existing opportunity estimate, not rederived
from the adjusted components. The former uniform age multiplier on innings and
all counts is removed for pitchers; it canceled out of ERA and WHIP.

Pitchers use 5/4/3 evidence weights, 200-IP regression, and a league baseline
from the full historical sample population. Every pitcher with positive innings
or batters faced in any prior season can receive a projection, including
relievers and pitchers whose appearances recorded no outs. No seasonal workload
or reliability cutoff applies. All available history contributes, including
outless seasons and seasons with other teams. Trade stints are combined first.
Weights remain attached to calendar years
when a pitcher misses a season; a missing year does not promote an older
season into the latest-year slot. Pitcher exports include PlayerID for matching. The reviewed marcelR 3/2/1 weights, 804 weighted
regression outs, role-based playing time, and population rebaselining are not yet
implemented. Historical published forecasts are therefore comparison targets,
not exact expected matches.


## Projected innings

Starting with 0.4.3, projected innings are:

```text
IP = (0.5 × IP in year−1 + 0.1 × IP in year−2 + 60) × default_ip_growth
```

Missing calendar years contribute zero without promoting older seasons. The
third prior season still contributes to regression evidence and reliability,
but contributes no innings to this playing-time estimate. A pitcher whose only
history is a 180-IP season three years ago now projects for 60 IP, rather than
180. With 181 IP last year and 185 IP two years ago, the formula gives 169 IP.

Apply each regressed per-IP count rate to the projected innings, then age the
performance components. This changes counting-stat totals while preserving
regressed rates and reliability. The same formula is used by player, team, and
batch projections. `MarcelConfig.season_weights` controls regression evidence;
`default_ip_growth` scales the final playing-time estimate (default 1.0).

The 60-IP allowance is a fixed modeling choice. It does not establish a current
roster spot, distinguish starters from relievers, or account for injuries and
retirement. Use a dated status snapshot to control target-season inclusion. This implements
the playing-time alternative identified in the projection math audit; the matching
example alone does not establish Baseball Reference or marcelR equivalence.


## Expanded pitcher statistics

Pitching.csv must now include W, L, SV, R, IBB, HBP, BK, and WP. Aggregate all
stints and project those counts using the existing per-IP weighting/regression
and playing-time scale. W/L/SV retain that contextual projection without a
separate age multiplier. The additional harmful-event counts R/IBB/HBP/BK/WP
use the reciprocal age factor. This is an extension of the existing model, not
an assertion that wins, saves, or balks follow a validated marcelR forecast.

Rates use full-precision totals and true decimal innings:

- W-L% = W/(W+L), displayed as a fraction with three decimals.
- ERA = 9*ER/IP; WHIP = (H+BB)/IP.
- H9, HR9, BB9, SO9 = 9 times the respective count divided by IP.
- SO/W = SO/BB, including intentional walks within BB once.

ERA has two display decimals, WHIP three, per-nine rates one, and SO/W two.
Undefined W-L% (no decisions) and SO/W (no walks) are NaN internally and blank in
exports. Existing zero-IP ERA/WHIP/per-nine behavior remains zero. R is total
runs allowed, not a substitute for ER. All counts remain unrounded internally.

## Batch calculation

`project_team` computes pitcher evidence, regression, aging, and derived rates
with grouped column operations, avoiding one `project_player` call per pitcher.
It retains the shared league baseline, calendar weights, latest three records,
first-appearance player order, and latest-record name and complete birth date. PlayerID
(or IDfg for older callers) separates pitchers who share a name.

Parity tests compare every output column against the single-player calculation,
including missing seasons, zero innings, undefined ratios, missing components,
custom configuration, and age boundaries. This optimization changes execution
cost without changing the pitching model.


## Confidence and target-season eligibility

Reliability is `weighted IP / (weighted IP + regression_ip)`. ConfidenceTier is
`core` at reliability >=0.50 and `low-sample` below it. With the default prior,
200 weighted innings is the boundary. Both tiers are projected and exported.
A one-out latest-season sample contributes 5/3 weighted innings; its reliability
is about 0.00826. A pitcher who faced a batter but recorded no outs can have zero
reliability and still receive a projection under the regression prior.

Dated eligibility snapshots (`--eligibility-file` and `--as-of`) use the same
schema as hitting. They filter output and target-date team membership, with
EligibilityAsOf included in exports. The full lookback sample population still
supplies league regression rates, so a roster filter cannot change a retained
pitcher's forecast. Without a snapshot, output is a historical candidate list;
it does not infer active roster, free-agent, retirement, or role status. A
position player with recorded pitching can therefore appear unless excluded by
the supplied eligibility decisions.
