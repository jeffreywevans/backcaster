from pathlib import Path

import pandas as pd
import pytest

from backcaster.gui import load_choices, load_settings, save_settings
from backcaster.outputs import to_csv, to_html


def test_folder_preferences_roundtrip_and_corruption(tmp_path: Path) -> None:
    config = tmp_path / "config" / "settings.json"
    values = {"output_dir": str(tmp_path / "Reports ü"), "data_dir": "local-data"}
    save_settings(config, values)
    assert load_settings(config) == values
    config.write_text("{broken", encoding="utf-8")
    assert load_settings(config) == {}
    config.write_text('["unexpected"]', encoding="utf-8")
    assert load_settings(config) == {}


def test_choices_from_local_data(tmp_path: Path) -> None:
    pd.DataFrame([{"playerID": "test01", "nameFirst": "Test", "nameLast": "Player"}]).to_csv(
        tmp_path / "People.csv", index=False
    )
    for table in ("Batting", "Pitching"):
        pd.DataFrame([{"yearID": y, "teamID": "BOS"} for y in (2020, 2021, 2022, 2024)]).to_csv(
            tmp_path / f"{table}.csv", index=False
        )
    seasons, players, teams = load_choices(str(tmp_path))
    assert seasons == ["2023"]
    assert players == ["Test Player [test01]"]
    assert teams == ["BOS"]


@pytest.mark.parametrize("renderer,extension", [(to_csv, "csv"), (to_html, "html")])
def test_gui_export_respects_explicit_root(tmp_path: Path, renderer, extension: str) -> None:
    working = tmp_path / "working"
    working.mkdir()
    selected = tmp_path / "chosen"
    selected.mkdir()
    import os

    os.chdir(working)
    data = pd.DataFrame([{"Name": "=Test", "PlayerID": "test01", "Year": 2023, "HR": 20.2}])
    destination = selected / f"report.{extension}"
    with pytest.raises(ValueError, match="current working directory"):
        renderer(data, destination)
    assert renderer(data, destination, output_root=selected) == destination
    assert destination.is_file()
    with pytest.raises(ValueError, match="selected output folder"):
        renderer(data, selected / ".." / f"escape.{extension}", output_root=selected)
    if extension == "csv":
        assert "'=Test" in destination.read_text()
