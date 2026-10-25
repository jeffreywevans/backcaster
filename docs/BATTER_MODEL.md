# Batter projection method

The local Lahman CLI uses the population-level pipeline in `backcaster.batters`.
It implements the six stages in the user-supplied Tango 2004 batter recipe, with
explicit choices where that summary does not specify mechanics. Baseball Reference
remains the validation target; this implementation does not claim exact parity.
Pitching retains its existing weights and regression settings, with separate
[real-age performance adjustments](PITCHER_MODEL.md).

We subsequently reviewed Ben Dilday's marcelR implementation as a reference.
See [source and adaptation notes](MARCELR_REFERENCE.md) for provenance, thanks,
license attribution, and differences from this implementation.

## Python API and configuration

Use `backcaster.batters.project_batters(seasons, year)` with the full non-pitcher
population, then filter its results for a player or team. `LahmanSource.project`
performs this population projection and selection for CLI commands.

The legacy `project_player(..., kind="batting")` and
`project_team(..., kind="batting")` paths have been removed. They now raise
`ProjectionError` directing callers to `project_batters`; their flat aging
multiplier changed playing time while canceling out of rates.

`MarcelConfig` configures pitching only: `season_weights`, `regression_ip`, and
`default_ip_growth`. Its unused batting fields `regression_pa`,
`default_pa_growth`, and `age_adjustment_fn` have been removed. Batter weights,
regression PA, playing time, and age adjustments follow the fixed rules below.

## Inputs and eligibility

Batting now requires `Appearances.csv` (`playerID`, `yearID`, `G_all`, `G_p`) and
`People.csv.birthYear`, in addition to the existing tables. Files must be from the
same edition. Read only the three completed seasons preceding the projection year.
Unknown or implausible birth years produce an error instead of silently assuming 29.

Aggregate trade stints first. Define a primary pitcher as someone pitching in more
than half of their appearances that season; exclude that player-season from batting
league context and projections. This is a documented classification choice rather
than a claim about Baseball Reference's exact classification. It retains hitters
with occasional pitching appearances and most two-way hitters.

Use all other positive-PA player-seasons for regression and rebaselining, including
unqualified players. Apply the existing qualification filter only when selecting
outputs: all commands select players qualifying in at least one of the three
prior seasons and use their available history, including nonqualified seasons. Team IDs and last-stint membership rules are unchanged.
The rebaselining population is independent of the command and requested team.

## Calculation

1. Weight the actual calendar seasons 5/4/3. Missing seasons contribute zero rather
   than shifting an older season into a more recent weight slot.
2. Compute each season's non-pitcher league event rates. Weight those rates by each
   player's own `season PA × season weight` to obtain their league-average exposure.
3. Add 1,200 PA at those player-specific league rates to the weighted evidence.
   Reliability is `weighted PA / (weighted PA + 1200)`.
4. Set projected PA to `0.5 × latest PA + 0.1 × preceding PA + 200`. Missing-year PA
   is zero. Do not use actual statistics from the projected year.
5. Compute age as `projection year − birthYear`. Set the signed adjustment to
   `(age − 29) × .003` above 29, or `(age − 29) × .006` otherwise. Multiply singles,
   doubles, triples, HR, BB, and HBP rates by `1 − adjustment`, and strikeout/other
   AB-out rates by `1 + adjustment`. Leave sacrifice rates neutral, then normalize
   to preserve each player's PA. This choice applies aging to skill rather than
   multiplying every count and denominator by the same factor, which would leave
   all rates unchanged. The exact event-specific treatment is not specified in
   the supplied recipe and may differ from Baseball Reference.
6. Rebaseline the entire projected non-pitcher population to the latest completed
   season's league event rates. Iterative proportional fitting adjusts the event
   matrix until league totals match at fixed player PA. This is our explicit
   interpretation of rebaselining; it avoids incompatible AB, hits, and PA totals.
   Fail if it does not converge. Select the requested qualified players afterward.

The mutually exclusive events are singles, doubles, triples, HR, BB, HBP, SO, SH,
SF, and remaining AB outs. Reconstruct H and AB and derive TB and recompute BA/OBP/SLG/OPS after
rebaselining. All counts retain decimal precision; no rounding enters the formulas.

## Validation

Hand-calculated fixtures exercise player-specific regression, PA, age direction,
calendar-year gaps, future-data exclusion, and conservation of league rates/player
PA. Integration tests check qualification, primary-pitcher exclusion, the effect
of unqualified players on league context, command consistency, and file errors.

A manual 2025 check against Lahman CSVs distributed by Rdatasets produced Betts:
527.3 PA, 24.27 HR, .278 AVG, .362 OBP, .507 SLG, .869 OPS, .8583 reliability.
The supplied Baseball Reference table has 527 PA, 24 HR, .281/.365/.512/.877 and
86% reliability. Tango age is 33 for Betts (born 1992), while the reference displays
32. These results are close but not equal; do not tune constants to a single player.
The check uses an independently obtained Lahman edition, not the user's local copy.


## Expanded counting statistics

Batting.csv must include R, RBI, SB, CS, IBB, and GIDP alongside the original
components. Trade aggregation sums them before projection. GIDP is mapped to GDP.
The shared schema in `stat_columns.py` controls model and report ordering.

Project R/RBI/SB/CS/GDP/IBB using the same calendar weights, exposure-specific
league regression, projected PA, and age model as the batter pipeline. They are
separate overlapping counts: never include them in the mutually exclusive PA
event matrix or its normalization. R/RBI/SB/IBB use the beneficial age direction;
CS/GDP use the harmful direction. The GDP age direction is an explicit modeling
choice, not a verified marcelR formula. These projections do not model lineup
position, baserunning opportunities, teammates, or managerial intent separately.

Rebaseline R/RBI/SB/CS independently to their latest-season league rate per PA.
IBB and GDP use bounded proportional scaling: preserve each league target while
keeping IBB <= BB and GDP <= non-strikeout AB outs for every player. Historical
counts must be finite/nonnegative and respect those subset relationships. Blank
historical numeric cells still follow the existing zero-fill policy.

Derive H and AB from the projected PA events, and TB from the projected base-hit
components. BA replaces AVG in canonical batter output. The formulas are:

- TB = H + 2B + 2*3B + 3*HR (equivalently 1B + 2*2B + 3*3B + 4*HR).
- BA = H/AB; SLG = TB/AB.
- OBP = (H+BB+HBP)/(AB+BB+HBP+SF), with IBB counted within BB once.
- OPS = OBP+SLG.

The new contextual projections do not change existing H/AB/BB/HBP/SF outcomes
or batting rates; they do not create additional hits or PA. Compute all derived
values before output rounding, including TB.
