from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import pytest
from tools.marcel_reference import (
    clean_archive,
    load_reference,
    match_reference,
    parse_innings,
    score_comparison,
)


def test_clean_archive_keeps_same_name_players_and_strips_spreadsheet_columns(tmp_path):
    archive = tmp_path / "marcel.zip"
    with ZipFile(archive, "w") as zip_file:
        zip_file.writestr(
            "2026 projections batter.csv",
            (
                "Name,Age,B,AB,H,OPS,Rel,\n"
                "Max Muncy,35,L,400,100,0.800,80%,\n"
                "Max Muncy,35,L,400,100,0.800,80%,\n"
                "Max Muncy,23,R,300,69,0.700,48,\n"
                ",,,,,,,\n"
                "José Example,24,S,300,50,0.600,0.66,\n"
            ).encode("cp1252"),
        )
    destination = tmp_path / "refs"
    manifest = clean_archive(archive, destination)
    result = pd.read_csv(destination / "2026-batting.csv")
    assert result.columns.tolist() == ["Year", "Name", "Age", "Reliability", "AB", "H", "OPS"]
    assert result["Name"].tolist() == ["Max Muncy", "Max Muncy", "José Example"]
    assert result["Reliability"].tolist() == [0.80, 0.48, 0.66]
    assert manifest["files"][0]["duplicate_rows"] == 1
    assert manifest["files"][0]["blank_rows"] == 1
    assert clean_archive(archive, destination) == manifest
    assert len(load_reference(destination, 2026, "batting")) == 3
    with pytest.raises(ValueError, match="reference manifest"):
        load_reference(destination, 2025, "batting")
    (destination / "2026-batting.csv").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="checksum mismatch"):
        load_reference(destination, 2026, "batting")


def test_clean_archive_preserves_historical_batting_ids_and_derives_rates(tmp_path):
    archive = tmp_path / "marcel.zip"
    with ZipFile(archive, "w") as zip_file:
        zip_file.writestr(
            "2008 projections batter.csv",
            "nameLast,nameFirst,playerID,Age,year, reliability ,mAB,mH,m2B,m3B,mHR,mBB,mHBP,mSF\n"
            "Example,Ana,exampan01,30,2008,-,400,100,20,2,10,45,3,2\n",
        )
    clean_archive(archive, tmp_path / "refs")
    row = pd.read_csv(tmp_path / "refs" / "2008-batting.csv").iloc[0]
    assert row.PlayerID == "exampan01"
    assert pd.isna(row.Reliability)
    assert row.TB == 154
    assert row.BA == 0.250
    assert row.OPS == 0.714


def test_modern_name_matching_disambiguates_and_reports_unknown_players():
    projected = pd.DataFrame(
        {
            "Name": ["Max Muncy", "Max Muncy", "Ronald Acuna", "J. T. Chargois"],
            "Age": [35, 23, 28, 35],
            "PlayerID": ["muncyma01", "muncyma02", "acunaro01", "chargjt01"],
        }
    )
    reference = pd.DataFrame(
        {
            "Name": ["Max Muncy", "Max Muncy", "Ronald Acuña Jr.", "JT Chargois", "Other"],
            "Age": [23, 35, 28, 35, 29],
        }
    )
    matched = match_reference(reference, projected)["PlayerID"]
    assert matched.iloc[:4].tolist() == ["muncyma02", "muncyma01", "acunaro01", "chargjt01"]
    assert pd.isna(matched.iloc[4])


def test_pitch_comparison_keeps_outs_and_scores_whole_innings():
    projected = pd.DataFrame(
        {"Name": ["Example"], "PlayerID": ["examp01"], "IP": [25 + 2 / 3], "ERA": [3.05]}
    )
    reference = pd.DataFrame({"PlayerID": ["examp01"], "IP": [26], "ERA": [3.1]})
    metrics, detail = score_comparison(projected, reference, "pitching")
    assert metrics.loc["IP", "MAE"] == pytest.approx(1 / 3)
    assert metrics.loc["IP (whole)", "exact"] == 1
    assert detail.loc["examp01", ("Delta", "ERA")] == pytest.approx(-0.05)
    with pytest.raises(ValueError, match="extra outs"):
        parse_innings(pd.Series([25.3]))


def test_cleaner_rejects_conflicting_player_rows_before_writing(tmp_path: Path):
    archive = tmp_path / "marcel.zip"
    with ZipFile(archive, "w") as zip_file:
        zip_file.writestr(
            "2025 projections pitcher.csv",
            "Name,Age,T,IP,ERA,Rel\nExample,32,R,25,3.00,44%\nExample,32,R,26,3.00,44%\n",
        )
    destination = tmp_path / "refs"
    with pytest.raises(ValueError, match="conflicting player identity"):
        clean_archive(archive, destination)
    assert not destination.exists()
