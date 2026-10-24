# Using the SABR Lahman database

The supplied [SABR Lahman README](lahman-readme2025.txt) describes the
**1871–2025 edition**, released December 10, 2025. It is retained unchanged as
the source reference for the database's table definitions, credits, and caveats.
The official database site is <https://sabr.org/lahman-database/>.

## Local setup

Use the comma-delimited CSV distribution, rather than the Access or MSSQL files.
Extract the files directly into a directory such as `C:\Baseball\lahman`.
This is the default directory on Windows. Elsewhere the default is
`~/Baseball/lahman`. Use `LAHMAN_DATA_DIR` or `--data-dir` to select another
location. All commands run offline, including when no `--data-dir` is supplied.
Backcaster needs `People.csv`, `Teams.csv`, and `Batting.csv` or `Pitching.csv`,
depending on the projection kind. Both kinds require `People.csv.birthYear`
for age adjustment. Batters also require `Appearances.csv` for pitcher classification; see
[the batter model](BATTER_MODEL.md). Keep those files from the same database edition.

```powershell
backcaster player --name "Mookie Betts" --year 2022 --kind batting --data-dir "C:\Baseball\lahman"
```

The target projection year needs the preceding three seasons. The 2025 edition
can supply 2023–2025 data for a 2026 projection, subject to player qualification
and data availability. It cannot supply 2026 statistics for a 2027 projection.
See the [offline usage guide](../README.md#offline-projections-with-lahman-csvs)
for qualification thresholds, Lahman team IDs, and treatment of traded players.

## Historical data caveats

The database includes historical major leagues and Negro League records under
SABR's definitions. Those definitions can differ from other data providers, and
historical research can revise the records. Negro League data comes from Seamheads.

The source README explicitly says that NULL values mean **unknown**, not zero.
Backcaster currently fills blank numeric counting-stat cells with zero, so
projections from incomplete records can be misleading. Prefer complete seasons
for projection work; that implementation choice does not change the meaning of
missing values in the source database.

The source also notes that player statistics may not sum to team totals when
records are incomplete, and that player and team records can cover different
sets of games. Backcaster's single season-wide qualification threshold is not
a reconstruction of each historical league's eligibility rules. Review the
source README's section 2.1 before interpreting historical Negro League results.

## Attribution and license

The supplied README credits copyright **1996–2025 SABR**, through Sean Lahman's
donation, and licenses the database under
[Creative Commons Attribution-ShareAlike 3.0 Unported](https://creativecommons.org/licenses/by-sa/3.0/).
Preserve the source credits and follow that license when redistributing or
adapting the database. Backcaster's MIT license does not replace the database's
license. Only the supplied README is included here; the CSV database is not bundled.
