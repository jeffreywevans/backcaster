# Third-party acknowledgments and notices

## marcelR — Ben Dilday

Backcaster is a Python implementation of Marcel-style baseball projections.
[marcelR](https://github.com/bdilday/marcelR), by Ben Dilday, is an independent R
implementation we reviewed as a methodological reference and source of inspiration.
Thank you to Ben Dilday for sharing readable formulas, intermediate calculations,
and historical comparison examples that help make this work reproducible.

Reference revision: `13a1c7943f5a7317c9c812a28e299c2184060046` (March 1, 2020).
See [reference and adaptation notes](docs/MARCELR_REFERENCE.md) for the files
reviewed, formulas examined, current differences, and attribution practices.

At the time this notice was added, marcelR source had been inspected, but no R
source had been copied or translated into Backcaster, and its datasets had not
been bundled. Backcaster does not depend on R or marcelR. The notice is retained
for acknowledgment and to accompany future attributed adaptations. Neither the
review nor the acknowledgment implies endorsement or verified numerical parity.

The following is marcelR's MIT license notice, reproduced without changes:

```text
MIT License

Copyright (c) 2017 Ben Dilday

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Method and data credits

Tom Tango developed the Marcel projection system. We thank him for publishing
its methodology. SABR, Sean Lahman, and the contributors to the Lahman database
provide the historical data on which local projections rely. The Lahman data
license is separate; see [database attribution and caveats](docs/LAHMAN.md).
