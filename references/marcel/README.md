# Marcel forecast benchmarks

These tables are reference forecasts for testing a Backcaster build. Run Backcaster against the three completed MLB seasons preceding the forecast year, then measure agreement with the matching Marcel release.

## Run against a build

Use the Python environment containing the Backcaster build you want to check. That can be an editable checkout or a virtual environment with a wheel installed. From the repository root, prepare the reference once using your copy of `marcel.zip`.

```sh
python tools/marcel_reference.py clean /path/to/marcel.zip
```

Run any covered season or inspect one player by Lahman ID.

```sh
python tools/marcel_reference.py compare --year 2025 --kind batting --data-dir /path/to/lahman
python tools/marcel_reference.py compare --year 2025 --kind batting --player-id muncyma01 --data-dir /path/to/lahman
python tools/marcel_reference.py compare --year 2025 --kind pitching --data-dir /path/to/lahman
```

`LAHMAN_DATA_DIR` also works. Use `--reference-dir` on both commands to point at another local reference folder, such as a checkout of a private archive. The default data folder is `references/marcel/data/`. Keep this folder outside public source control unless the relevant redistribution rights are confirmed. The original ZIP is an input to `clean`.

The comparator runs the normal full-population batch forecast, including for single-player comparisons. It reports matched and unmatched coverage, exact displayed values, mean absolute error (MAE), signed bias, and the largest errors. Signed differences are Backcaster minus Marcel. Missing published statistics are excluded from the applicable metric. Reliability is compared to two decimal places. For whole-inning releases, the separate `IP (whole)` comparison rounds Backcaster to that precision. The `IP` comparison uses its exported outs and expresses differences in decimal innings.

## Archive and provenance

The supplied archive contains one batting and one pitching table per season for 2001–2012 and 2024–2027. `clean` produces one UTF-8 CSV per year and kind plus `manifest.json` with source and output hashes and row counts. The comparator verifies those checksums when a manifest is present. The [archive manifest](archive-manifest.json) records the supplied archive. It removes exact duplicates and blank records, drops batting `B` and pitching `T` handedness, and keeps actual statistics such as runs and losses. For early batting files, the cleaner derives TB, BA, OBP, SLG and OPS from the published counting stats. Historical pitcher ERA is retained as printed, including the releases with a BaseRuns component. Missing values stay blank.

Historical files carry Lahman player IDs. Recent files are joined on normalized names or verified name variants. Where names collide, the comparison uses published age to disambiguate and reports unresolved rows as reference-only. Raw archive coverage does not always match Backcaster's historical candidate list. Record the Lahman edition alongside any saved result. The 2027 forecast needs 2026 actuals. One audit using the Rdatasets copy of Lahman through 2025 needed five missing non-pitcher appearance rows repaired from the same edition's batting and pitching tables for the 2026 batting run.

The early archive follows [Tango's published tables](https://www.tangotiger.net/marcel/). The later tables follow the [Baseball Reference Marcel release format](https://www.baseball-reference.com/leagues/majors/2025-projections.shtml). The source ZIP and cleaned tables are distinct from the Backcaster software license. [Sports Reference data use policy](https://www.sports-reference.com/data_use.html).

## Batting punch list

1. Establish an OPS baseline for the recent releases. Start with the observed .003–.004 mean absolute difference and review the largest errors and coverage alongside it. In 2025, 347 of 504 matched hitters were within three OPS points and the 90th-percentile error was eight points.
2. Preserve the current PA and reliability structure as the baseline. All 10,199 matched 2001–2012 PA forecasts reproduce with half-to-even rounding. Test recent PA rounding on a whole release before changing the report globally. Compare BA, OBP, SLG, and OPS after rounding the counting stats, as in the recent tables.
3. Test age used by the model and age displayed in the report independently. Keep June 30 as the recent report convention. Test birth-year age in the model on seasons held out of calibration. Across 2024–2026 it reduced hit MAE from 0.329 to 0.287 and strikeout MAE from 0.339 to 0.287 per batter.
4. Inspect the source of remaining count errors before adjusting the aging slopes. Test league rebaselining, the pitcher-batting filter, and at-bat rounding. The early release group averaged 0.61 extra hits and 0.88 fewer strikeouts per batter in Backcaster.

## Pitching punch list

1. Implement the role-based workload estimate first. Project IP as `0.5 × last IP + 0.1 × preceding IP + 25 + 35 × weighted GS/G` with starts and games separately weighted 3/2/1. The candidate reduced average innings error from 23.71 to 0.22 for 2001–2012 and from 21.78 to 0.26 for 2024–2026. Retain one-out precision for Backcaster and compare at whole-inning precision where the reference warrants it.
2. Reproduce reliability by release. Use `weighted evidence / (weighted evidence + prior)` with 3/2/1 weights. The early tables use an 800-out prior and the recent tables use a 1,200-batters-faced prior. These rules reproduced every matched published value in their respective groups. Test the two published conventions explicitly before choosing defaults for seasons without a reference.
3. Test league baselines, the performance regression denominator, and aging after workload and reliability agree. Compare BF, strikeouts, walks, home runs, ERA and WHIP, and review starters, relievers, and hybrid roles. For early releases, account for the published blend of projected ER and BaseRuns ER when comparing ERA.
4. Benchmark 2027 once a verified 2026 input edition is available. Keep that release available as a check on rules chosen from the earlier seasons.
