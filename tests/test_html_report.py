from html.parser import HTMLParser
from pathlib import Path

import pandas as pd

from backcaster.outputs import to_html


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.headers = []
        self.cells = []
        self.tags = []
        self.header = False
        self.cell = False

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        if tag == "th":
            self.header = True
            self.headers.append("")
        if tag == "td":
            self.cell = True
            self.cells.append("")

    def handle_endtag(self, tag):
        if tag == "th":
            self.header = False
        if tag == "td":
            self.cell = False

    def handle_data(self, data):
        if self.header:
            self.headers[-1] += data
        if self.cell:
            self.cells[-1] += data


def test_identity_first_and_batting_order(tmp_path: Path) -> None:
    frame = pd.DataFrame(
        [
            dict(
                HR=45.6,
                OPS=1.048,
                Age=33,
                PA=598.2,
                PlayerID="judgeaa01",
                Year=2025,
                Name="Aaron Judge",
                BA=0.293,
                Reliability=0.86,
            )
        ]
    )
    original = frame.copy(deep=True)
    text = to_html(frame, tmp_path / "hitters.html").read_text()
    parser = TableParser()
    parser.feed(text)
    assert parser.headers == [
        "Name",
        "Year",
        "Player ID",
        "Age",
        "PA",
        "HR",
        "BA",
        "OPS",
        "Reliability",
    ]
    assert parser.cells == [
        "Aaron Judge",
        "2025",
        "judgeaa01",
        "33",
        "598",
        "46",
        "0.293",
        "1.048",
        "0.860000",
    ]
    assert "<!doctype html>" in text
    assert "<style>" in text
    assert "Batting projections" in text
    assert "Showing 1 of 1 players" in text
    assert "https://" not in text
    pd.testing.assert_frame_equal(frame, original)


def test_pitching_order_precision_and_notes(tmp_path: Path) -> None:
    frame = pd.DataFrame(
        [
            dict(
                WHIP=1.234,
                ERA=3.456,
                Name="Example",
                Age=30,
                Year=2025,
                PlayerID="test01",
                BF=700.4,
                SO=200.5,
                BB=50.3,
                HR=20.3,
                H=130.2,
                ER=60.7,
                IP=161 + 1 / 3,
            )
        ]
    )
    text = to_html(frame, tmp_path / "pitchers.html").read_text()
    parser = TableParser()
    parser.feed(text)
    assert parser.headers == [
        "Name",
        "Year",
        "Player ID",
        "Age",
        "ERA",
        "IP",
        "H",
        "ER",
        "HR",
        "BB",
        "SO",
        "BF",
        "WHIP",
    ]
    assert parser.cells[4:] == ["3.46", "161.1", "130", "61", "20", "50", "201", "700", "1.234"]
    assert "Pitching projections" in text
    assert ".1 is one out" in text


def test_missing_metadata_unknown_columns_and_empty_report(tmp_path: Path) -> None:
    frame = pd.DataFrame([{"Name": None, "PA": 100, "Other": 1.23456789}])
    parser = TableParser()
    parser.feed(to_html(frame, tmp_path / "partial.html").read_text())
    assert parser.headers[:4] == ["Name", "Year", "Player ID", "Age"]
    assert parser.cells[:4] == ["", "", "", ""]
    assert parser.cells[-1] == "1.234568"
    text = to_html(pd.DataFrame(), tmp_path / "empty.html").read_text()
    assert "No players to display." in text
    assert "Showing 0 of 0 players" in text


def test_html_escapes_values_and_column_names(tmp_path: Path) -> None:
    name = '<script>alert("bad")</script>'
    column = '<img src=x onerror="bad()">'
    frame = pd.DataFrame([{"Name": name, "Year": "<b>2025</b>", column: "<svg/onload=bad()>"}])
    # Year is numeric in projections; use a valid year and inject through a generic column.
    frame["Year"] = 2025
    text = to_html(frame, tmp_path / "escaped.html").read_text()
    parser = TableParser()
    parser.feed(text)
    assert parser.cells[0] == name
    assert parser.headers[-1] == column
    assert parser.cells[-1] == "<svg/onload=bad()>"
    assert "img" not in parser.tags
    assert "svg" not in parser.tags
    assert parser.tags.count("script") == 1  # Only the trusted report script.
    assert "<script>alert(" not in text


def test_historical_comparison_rows_and_variance_colors(tmp_path: Path) -> None:
    projections = pd.DataFrame(
        [
            dict(
                Name="Aaron Example",
                Year=2022,
                PlayerID="example01",
                Age=30,
                PA=100.0,
                HR=10.0,
                BA=0.250,
                Reliability=0.8,
            ),
            dict(
                Name="No Actual",
                Year=2022,
                PlayerID="missing01",
                Age=28,
                PA=50.0,
                HR=2.0,
                BA=0.200,
                Reliability=0.2,
            ),
        ]
    )
    actuals = pd.DataFrame(
        [
            dict(
                Name="Aaron Example",
                Year=2022,
                PlayerID="example01",
                Age=30,
                PA=110.0,
                HR=8.0,
                BA=0.275,
            )
        ]
    )

    text = to_html(projections, tmp_path / "accuracy.html", actuals).read_text()
    parser = TableParser()
    parser.feed(text)

    assert text.count('class="compare-toggle"') == 2
    assert text.count('class="compare-toggle" aria-expanded="false"') == 2
    assert text.count('data-expanded="false"') == 2
    assert 'id="actual-0" hidden' in text
    assert 'id="variance-0" hidden' in text
    assert 'id="actual-1" hidden' in text
    assert 'id="variance-1" hidden' in text
    assert 'aria-label="Show historical comparison for Aaron Example"' in text
    assert 'id="expand-all" aria-controls="projections">Expand all</button>' in text
    assert 'id="collapse-all" aria-controls="projections">Collapse all</button>' in text
    assert 'aria-controls="actual-0 variance-0"' in text
    assert text.count('class="detail-row actual-row"') == 2
    assert text.count('class="detail-row variance-row"') == 2
    assert "Actual (no recorded stats)" in parser.cells
    assert "Variance" in parser.cells
    assert ">+10</td>" in text
    assert 'class="variance-negative">-2</td>' in text
    assert 'class="rate variance-positive">+0.025</td>' in text
    assert text.index(".rate {") < text.index(".variance-positive {")
    assert "Variance is actual minus projected" in text
    assert "Projection, actual, and variance rows" in text


def test_historical_comparison_escapes_toggle_attributes(tmp_path: Path) -> None:
    name = "A &quot; <script>"
    projections = pd.DataFrame([dict(Name=name, Year=2022, PlayerID="safe01", Age=30, PA=100)])
    actuals = projections.copy()
    text = to_html(projections, tmp_path / "safe.html", actuals).read_text()
    assert 'data-name="A &amp;quot; &lt;script&gt;"' in text
    assert "<script>" not in text.split("<script>", 1)[0]


def test_projection_only_report_has_no_comparison_controls(tmp_path: Path) -> None:
    frame = pd.DataFrame([dict(Name="Player", Year=2022, PlayerID="p", Age=30, PA=100)])
    text = to_html(frame, tmp_path / "projections.html").read_text()
    assert 'id="expand-all"' not in text
    assert 'id="collapse-all"' not in text
    assert 'class="compare-toggle"' not in text
