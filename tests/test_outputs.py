import re
from pathlib import Path

import pandas as pd
import pytest

from backcaster.outputs import _display_frame, _format_innings, to_cli_table, to_csv, to_html


def test_csv_output_creation(tmp_path: Path) -> None:
    df = pd.DataFrame([{"Name": "A", "PA": 100}])
    out = tmp_path / "out.csv"
    to_csv(df, out)
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "Name,PA" in content


def test_html_output_creation(tmp_path: Path) -> None:
    df = pd.DataFrame([{"Name": "A", "PA": 100}])
    out = tmp_path / "out.html"
    to_html(df, out)
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "<table" in content
    assert "A" in content


def test_cli_table_output() -> None:
    df = pd.DataFrame([{"Name": "A", "PA": 100}])
    assert to_cli_table(df) == df.to_string(index=False)


@pytest.mark.parametrize(
    "innings, expected",
    [
        (161, "161.0"),
        (161 + 1 / 3, "161.1"),
        (161 + 2 / 3, "161.2"),
        (161.999999, "162.0"),
        (161.5, "161.2"),
        (0, "0.0"),
        (1 / 3, "0.1"),
        (float("nan"), ""),
    ],
)
def test_baseball_innings_notation(innings: float, expected: str) -> None:
    assert _format_innings(innings) == expected


@pytest.mark.parametrize("innings", [-1, float("inf")])
def test_invalid_display_innings(innings: float) -> None:
    with pytest.raises(ValueError, match="finite, nonnegative"):
        _format_innings(innings)


def test_display_precision_and_no_mutation() -> None:
    frame = pd.DataFrame(
        [
            dict(
                Name="Judge",
                PlayerID="judgeaa01",
                PA=598.5,
                HR=45.6,
                H=143.2,
                AVG=0.293,
                OBP=0.415,
                SLG=0.633,
                OPS=1.048,
                ER=60.5,
                BB=51.1,
                SO=199.8,
                BF=700.4,
                IP=161 + 1 / 3,
                ERA=3.456,
                WHIP=1.234,
                Age=33.0,
                Year=2025,
                Other=1.234567,
            )
        ]
    )
    original = frame.copy(deep=True)
    result = _display_frame(frame).iloc[0]
    for column, expected in {
        "PA": "599",
        "HR": "46",
        "H": "143",
        "AVG": "0.293",
        "OBP": "0.415",
        "SLG": "0.633",
        "OPS": "1.048",
        "ER": "61",
        "BB": "51",
        "SO": "200",
        "BF": "700",
        "IP": "161.1",
        "ERA": "3.46",
        "WHIP": "1.23",
        "Age": "33",
        "Year": "2025",
    }.items():
        assert result[column] == expected
    assert result.Other == 1.234567
    pd.testing.assert_frame_equal(frame, original)


def test_missing_numbers_and_fixed_trailing_zeros() -> None:
    result = _display_frame(
        pd.DataFrame(
            [{"PA": float("nan"), "AVG": 0.3, "OBP": 0.0, "OPS": 1.0, "ERA": 4.0, "WHIP": 1.1}]
        )
    ).iloc[0]
    assert result.PA == ""
    assert result.AVG == "0.300"
    assert result.OBP == "0.000"
    assert result.OPS == "1.000"
    assert result.ERA == "4.00"
    assert result.WHIP == "1.10"


@pytest.mark.parametrize("output", ["cli", "csv", "html"])
def test_all_outputs_share_display_format(tmp_path: Path, output: str) -> None:
    frame = pd.DataFrame(
        [dict(Name="Example", HR=24.6, OPS=1.048, IP=161 + 2 / 3, ERA=3.456, WHIP=1.234)]
    )
    if output == "cli":
        text = to_cli_table(frame)
        for value in ["25", "1.048", "161.2", "3.46", "1.23"]:
            assert value in text
    elif output == "csv":
        path = to_csv(frame, tmp_path / "out.csv")
        row = pd.read_csv(path, dtype=str).iloc[0]
        assert row.HR == "25"
        assert row.OPS == "1.048"
        assert row.IP == "161.2"
        assert row.ERA == "3.46"
        assert row.WHIP == "1.23"
    else:
        text = to_html(frame, tmp_path / "out.html").read_text()
        for value in ["25", "1.048", "161.2", "3.46", "1.23"]:
            assert re.search(r"<td(?: [^>]*)?>" + re.escape(value) + r"</td>", text)
