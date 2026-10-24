# HTML reports

Generate reports through the existing CLI, for example:

```powershell
backcaster hitters --year 2025 --format html --out hitters_2025.html
backcaster pitchers --year 2025 --format html --out pitchers_2025.html
```

Each report is one HTML file with embedded CSS and vanilla JavaScript. It has no
external asset or network dependencies. Search, column sorting, reset, and browser
printing operate locally. The table remains readable if JavaScript is disabled.
The visual design uses a restrained enterprise reporting palette, light cards,
and compact striped tables, with no third-party branding or copied assets.

## Layout and constants

`src/backcaster/html_report.py` contains the report renderer and these constants:

- `IDENTITY_COLUMNS`: Name, Year, PlayerID, Age. They are always the first four
  columns; unavailable metadata displays as blank.
- `BATTING_COLUMNS` and `PITCHING_COLUMNS`: preferred counting-stat/rate order.
  Additional fields are preserved after known statistics.
- `COLUMN_LABELS` and `COLUMN_HELP`: display labels and column tooltips.
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
