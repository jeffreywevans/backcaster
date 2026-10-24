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
                AVG=0.293,
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
        "AVG",
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
        "IP",
        "ER",
        "H",
        "HR",
        "BB",
        "SO",
        "BF",
        "ERA",
        "WHIP",
    ]
    assert parser.cells[4:] == ["161.1", "61", "130", "20", "50", "201", "700", "3.46", "1.23"]
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
