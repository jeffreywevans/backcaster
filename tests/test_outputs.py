from pathlib import Path

import pandas as pd

from marcelball.outputs import to_cli_table, to_csv, to_html


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
