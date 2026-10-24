# Projection math audit

Baseball Reference's projections are the acceptance target for future model
alignment. The corrections below are incremental; the current implementation
does not yet reproduce that target. Validate both hitters and pitchers against
the reference before describing the model as equivalent.

The supplied Baseball Reference 2025 projection tables contain 504 hitters and
611 pitchers. They are reference forecasts, not prior-season input data, so they
cannot by themselves establish exact errors in individual Backcaster forecasts.
A player-level comparison also needs Backcaster's output and the same underlying
2022–2024 season records.

## Supplied player outputs

The user subsequently supplied these results from the old calculation:

| Player / statistic | Backcaster | Baseball Reference |
| --- | --- | --- |
| Mookie Betts PA | 609 (displayed rounded) | 527 |
| Mookie Betts OPS | .818137 | .877 |
| Mookie Betts reliability | .504792 | 86% |
| Kevin Gausman IP | 181.8345 | 169.0 |
| Kevin Gausman ERA | 3.555828 | 3.67 |
| Kevin Gausman reliability | .150625 | 79% |

The season counts were checked against the Lahman tables distributed by
[Rdatasets](https://github.com/vincentarelbundock/Rdatasets/tree/master/csv/Lahman).
Betts had 516, 693, and 639 PA in 2024, 2023, and 2022. Gausman recorded
543, 555, and 524 outs, or 181, 185, and 174 2/3 innings.

These inputs reproduce the old reliability exactly (within the supplied batting
rounding): Betts has a 605.75 weighted PA average, divided by 1,200 to give
.5047917. Gausman has a 180.75 weighted innings average, also incorrectly divided
by 1,200, to give .150625. The age-29 multiplier of 1.006 then reproduces
181.8345 projected innings and approximately 609 displayed PA.

With the regression correction and otherwise unchanged assumptions, reliability
becomes approximately 85.83% for Betts and 91.56% for Gausman. The latter still
differs from the reference's 79%; correcting this bug does not establish that
the pitching methodology matches Baseball Reference.

There is a separate playing-time difference. The hitter formula
`0.5 * last_year_PA + 0.1 * two_years_ago_PA + 200` gives Betts 527.3 PA,
matching the reference's rounded 527. The analogous pitcher calculation with a
60-IP constant gives Gausman `0.5 * 181 + 0.1 * 185 + 60 = 169` innings,
matching the reference. This correspondence identifies a concrete alternative
to the current weighted-average playing-time assumption; two matching examples
alone do not verify the reference's complete methodology.

## Corrected regression scale

With three seasons and weights 5/4/3, regression evidence must use weighted
**totals**, even when playing time is expressed as a weighted seasonal average.
Previously Backcaster divided weighted counts by 12 before adding the regression
sample, making regression 12 times stronger relative to the observed evidence.

For a hitter with 600 PA and 60 HR in each prior season, a league HR rate of 2%,
and 1,200 regression PA:

| Calculation | Previous | Corrected |
| --- | --- | --- |
| Evidence PA | 600 | 7,200 |
| Evidence HR | 60 | 720 |
| Regressed HR rate | (60 + 24) / 1,800 | (720 + 24) / 8,400 |
| HR per 600 projected PA | 28.00 | 53.14 |

This example holds playing time constant to isolate regression. It is not a
comparison for a named Baseball Reference player.

Reliability now represents the observed-evidence fraction:
`weighted playing time / (weighted playing time + regression playing time)`.
The example gives 85.71%, rather than the previous 50%. Pitching uses innings
and its innings regression constant, rather than a shared 1,200-unit scale.
The unused `MarcelConfig.reliability_scale` field was removed; reliability follows
the regression setting for the selected projection kind.

Hand-calculated tests cover batting, pitching, and a one-season input. The
batting-average, on-base, slugging, ERA, and WHIP arithmetic was not changed.

## Remaining differences and limitations

- **Eligibility:** Backcaster intentionally filters qualified player-seasons.
  The reference includes relievers (for example Bryan Abreu, projected for 71 IP)
  and players with shorter histories. The populations are different.
- **Age:** The local adapter does not yet supply birth-date-derived age. Calls
  default to age 29. The current adjustment is a two-level playing-time multiplier,
  applied to every component, so it cancels out of projected rates. It does not
  implement a full age-based skill adjustment.
- **Playing time and weights:** Backcaster uses a weighted seasonal average for
  playing time and 5/4/3 weights for both kinds. This audit does not establish
  that those assumptions match the reference's hitter and pitcher methodologies.
  Available seasons are ranked by recency, so a missing middle season is not
  assigned an explicit calendar-year weight.
- **Baseline:** Regression uses the pooled qualified-player input seasons. That
  may differ from the reference's league population, season weighting, and
  normalization. Filtering eligibility also changes regression rates.
- **Rounding:** Backcaster retains decimal counts and uses decimal innings
  internally. Baseball display notation such as `162.1` means 162 innings plus
  one out, not 162.1 decimal innings; convert it before numerical comparisons.

These remaining choices need explicit methodology decisions before claiming
Baseball Reference parity. A match in reliability or one statistic alone does
not establish equivalence.
