# marcelR reference and adaptation notes

## Reference inspected

- Project: [bdilday/marcelR](https://github.com/bdilday/marcelR)
- Author: Ben Dilday
- License: MIT; copyright (c) 2017 Ben Dilday
- Revision: [`13a1c7943f5a7317c9c812a28e299c2184060046`](https://github.com/bdilday/marcelR/tree/13a1c7943f5a7317c9c812a28e299c2184060046), dated March 1, 2020

We reviewed the R source and examples as a methodological reference, not as a
runtime dependency. Backcaster remains a Python project. This was a source review;
the R package was not executed as part of it. Thanks to Ben Dilday for making
marcelR available and exposing intermediate calculations rather than only results.

## How the reference informed our work

The initial Backcaster batter pipeline was written from the supplied Tango recipe
before this repository review. The review checked assumptions and identified
differences to investigate; it did not retroactively make that pipeline a port.

| Upstream file | Reference value |
| --- | --- |
| `R/marcelBatting.R` | 5/4/3 weighting, player-specific exposure-weighted league regression, 100 × 12 = 1,200 weighted regression PA, and projected PA |
| `R/marcelPitching.R` | 3/2/1 weighting, 134 × 6 = 804 weighted regression outs, and starter/reliever playing-time allowance |
| `R/utilities.R` | Reciprocal age adjustments, birth-year ages, and primary-position classification |
| `inst/scripts/marcel_data_exporter.R` | Choice of age-adjustment direction for beneficial versus harmful outcomes |
| `inst/scripts/compare_results.R` and `inst/extdata/*Marcel2004.csv` | Examples of comparisons against historical Tango projections; candidates for future validation, not data already incorporated into Backcaster |

For example, marcelR's pitcher playing-time formula uses outs throughout:

```text
0.5 × latest outs + 0.1 × preceding outs + 75 + 105 × latest GS/G
```

It adds 804 regression outs to weighted evidence, not 134. These are reviewed
reference formulas; the current Backcaster pitcher model has not yet adopted them.

The review also found differences from Backcaster's batter pipeline: marcelR
uses reciprocal age decline, independent per-stat rebaselining to a weighted
three-year league target, and `Fielding`-based primary positions. Backcaster's
current choices are documented in [the batter model](BATTER_MODEL.md).
They must not be described as equivalent without comparison tests.

## Attribution when adapting code

No marcelR R source was copied or translated for this documentation change, and
none of its data files are distributed here. Future adaptations should identify
the source file and pinned revision alongside the Python implementation, describe
substantive changes, and update these notes to distinguish reference-only work
from actual adaptations. Preserve Ben Dilday's copyright and the complete MIT
permission and warranty notice with copies or substantial portions of that work.

The full upstream license is retained in
[THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md), which is included as a license
file in both the wheel and source distribution. Backcaster's own MIT license is
retained separately. Database and benchmark-data licensing must be considered
separately from the software license before incorporating those files.

Tom Tango deserves credit for the Marcel system itself. Baseball Reference is
our comparison target; neither it nor the authors named here are represented as
endorsing Backcaster. Clear provenance and reproducible numerical checks take
priority over GUI work or new report formats.
