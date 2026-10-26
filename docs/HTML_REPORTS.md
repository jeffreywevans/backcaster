# HTML reports

In the desktop GUI (`backcaster-gui`, new in 0.5.0), generate a report and choose
**Export HTML** to save it within the selected report output folder. Set **Compare actual season** to **Yes** before generation to include actuals
and actual-minus-projected variance in the preview, HTML, and CSV exports.

Generate reports through the CLI, for example:

```powershell
backcaster hitters --year 2025 --format html --out hitters_2025.html
backcaster pitchers --year 2025 --format html --out pitchers_2025.html
backcaster hitters --year 2025 --format html --compare-actuals --out hitters_accuracy_2025.html
backcaster pitchers --year 2025 --format html --compare-actuals --out pitchers_accuracy_2025.html
```

Each report is one HTML file with embedded CSS and vanilla JavaScript. It has no
external asset or network dependencies. Search, column sorting, reset, and browser
printing operate locally. The table remains readable if JavaScript is disabled.
The visual design uses a restrained enterprise reporting palette, light cards,
and compact striped tables, with no third-party branding or copied assets.

Output paths must resolve within the current working directory or its
subdirectories. Run Backcaster from the intended output directory when exporting
elsewhere; parent traversal and symbolic links cannot escape this boundary.

## Layout and constants

`src/backcaster/stat_columns.py` defines the canonical batter/pitcher schemas
and identity columns shared by calculations and every output format.
`src/backcaster/html_report.py` contains the report renderer and these constants:

- `IDENTITY_COLUMNS` (imported): Name, Year, PlayerID, Age. They are always the first four
  columns; unavailable metadata displays as blank.
- `BATTING_COLUMNS` and `PITCHING_COLUMNS`: the shared canonical stat order.
  Additional fields are preserved after known statistics.
- `COLUMN_LABELS` and `COLUMN_HELP`: display labels and column tooltips.
- `TABLE_ROW_END`: the shared closing tag for projection and comparison rows.
- `REPORT_CSS`: theme, responsive layout, and print rules. Change the CSS custom
  properties in `:root` to adjust brand colors, surfaces, borders, and rounding.
- `REPORT_JS`: local search and sorting behavior; data is read from table cells
  rather than interpolated into executable JavaScript.

`outputs.py` formats a copy of the projection DataFrame before passing it to the
renderer. Counts and rate precision follow the shared CLI/CSV display rules;
projection values are not mutated. HTML-only column ordering does not reorder
the source DataFrame. Reliability retains its numeric observed-evidence scale.

## Reading and sharing

Select a column heading to toggle ascending/descending order. The heading exposes
its sort state to assistive technology. Search matches any displayed cell and
updates the visible-row count. Reset restores the original order and all rows.
Empty data and no-match filters have explicit messages.

Use horizontal scrolling on narrow screens; names and headings stay visible.
The print button opens the browser's print dialog, where saving as PDF may be
available. Print styles remove controls and expand the table beyond its screen
scroll region. Filtering and sort order are preserved for printing.

IP uses baseball notation even inside HTML: 161.1 means 161 innings and one out,
not 161.1 decimal innings. Rates are calculated before presentation rounding.
Player names, metadata, values, and column labels are HTML-escaped.

## Historical accuracy comparisons

New in 0.4.3: add `--compare-actuals` to an HTML command when the target season is present in
the local Lahman files. Projection calculations still read only the three prior
seasons. The report then adds two rows beneath every projected player:

- **Actual** contains the player's aggregated target-season results.
- **Variance** is `actual - projected`; positive values are green and negative
  values are red.

The button beside each player name expands or collapses that player's comparison.
Rows start collapsed. Use **Expand all** or **Collapse all** to change every player
at once, including players hidden by search. Individual triangles toggle just one
player. **Reset** clears search and sorting and collapses all comparisons. Rows
remain attached to their player during sorting and filtering,
and print in their current state. If Lahman has no target-season record for a
projected player, the report says `Actual (no recorded stats)` and leaves the
variance cells blank. This avoids treating a season without an appearance as a
zero-stat season.

For a 2025 comparison, supply 2022–2024 projection inputs plus 2025 batting or
pitching results and team game counts. This works with all CLI projection
commands and is rejected for CSV and terminal output. Actuals are matched by
PlayerID, combine all target-year stints, and do not require qualification.
Only projected players appear; actual results do not add new players.

Variances use full-precision values before formatting. Colors show direction,
not whether a result is better: positive ERA variance means a higher ERA than
projected. IP variances use signed baseball notation (`+1.2` means one inning
and two outs). Projection-only metadata such as ConfidenceTier and Reliability
is blank on actual and variance rows.
