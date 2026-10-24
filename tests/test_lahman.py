from pathlib import Path

import pandas as pd
import pytest

from backcaster.cli import main
from backcaster.data import DataFetchError, PlayerLookupError
from backcaster.lahman import LahmanSource
from backcaster.marcel import ProjectionError


@pytest.fixture
def lahman(tmp_path: Path) -> Path:
    pd.DataFrame(
        [
            {"playerID": "star", "nameFirst": "Test", "nameLast": "Star"},
            {"playerID": "other", "nameFirst": "Other", "nameLast": "Player"},
            {"playerID": "minor", "nameFirst": "Brief", "nameLast": "Career"},
        ]
    ).to_csv(tmp_path / "People.csv", index=False)
    batting, pitching, teams = [], [], []
    for year, games in [(2019, 162), (2020, 60), (2021, 162)]:
        teams.append({"yearID": year, "teamID": "BOS", "G": games})
        for player, ab, bb in [("star", 500, 60), ("other", 450, 70), ("minor", 20, 0)]:
            batting.append(
                dict(
                    playerID=player,
                    yearID=year,
                    stint=1,
                    teamID="BOS",
                    AB=ab,
                    H=150,
                    **{"2B": 30, "3B": 2},
                    HR=20,
                    BB=bb,
                    SO=100,
                    HBP=5,
                    SF=5,
                    SH=1,
                )
            )
            pitching.append(
                dict(
                    playerID=player,
                    yearID=year,
                    stint=1,
                    teamID="BOS",
                    IPouts=487 if player != "minor" else 10,
                    ER=60,
                    H=150,
                    HR=20,
                    BB=50,
                    SO=180,
                    BFP=700,
                )
            )
    pd.DataFrame(batting).to_csv(tmp_path / "Batting.csv", index=False)
    pd.DataFrame(pitching).to_csv(tmp_path / "Pitching.csv", index=False)
    pd.DataFrame(teams).to_csv(tmp_path / "Teams.csv", index=False)
    return tmp_path


def test_season_qualification_and_components(lahman: Path) -> None:
    source = LahmanSource(str(lahman))
    batting = source.season(2021, "batting").set_index("PlayerID")
    assert set(batting.index) == {"star", "other"}
    assert batting.loc["star", "PA"] == 571
    pitching = source.season(2021, "pitching").set_index("PlayerID")
    assert pitching.loc["star", "IP"] == pytest.approx(162 + 1 / 3)
    assert pitching.loc["star", "BF"] == 700


def test_traded_player_combined_before_qualification(lahman: Path) -> None:
    path = lahman / "Batting.csv"
    frame = pd.read_csv(path)
    row = frame[(frame.playerID == "star") & (frame.yearID == 2021)].copy()
    frame = frame.drop(row.index)
    for column in ["AB", "H", "2B", "3B", "HR", "BB", "SO", "HBP", "SF", "SH"]:
        row[column] = row[column] / 2
    second = row.assign(stint=2, teamID="LAN")
    pd.concat([frame, row, second]).to_csv(path, index=False)
    season = LahmanSource(str(lahman)).season(2021, "batting")
    star = season[season.PlayerID == "star"]
    assert len(star) == 1
    assert star.iloc[0]["PA"] == 571
    assert star.iloc[0]["Team"] == "LAN"


def test_short_season_threshold(lahman: Path) -> None:
    path = lahman / "Batting.csv"
    frame = pd.read_csv(path)
    frame.loc[frame.playerID == "star", ["AB", "BB", "HBP", "SF", "SH"]] = [190, 0, 0, 0, 0]
    frame.to_csv(path, index=False)
    source = LahmanSource(str(lahman))
    assert "star" in set(source.season(2020, "batting").PlayerID)
    assert "star" not in set(source.season(2021, "batting").PlayerID)
    with pytest.raises(ProjectionError, match="all three"):
        source.project("player", 2022, "batting", name="Test Star")


@pytest.mark.parametrize("command", ["player", "team", "batch"])
@pytest.mark.parametrize("kind", ["batting", "pitching"])
def test_offline_cli(
    lahman: Path, monkeypatch: pytest.MonkeyPatch, command: str, kind: str
) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("offline mode attempted network access")

    monkeypatch.setattr("socket.create_connection", forbidden)
    monkeypatch.setattr("socket.socket.connect", forbidden)
    out = lahman / "projection.csv"
    args = [
        command,
        "--year",
        "2022",
        "--kind",
        kind,
        "--data-dir",
        str(lahman),
        "--format",
        "csv",
        "--out",
        str(out),
    ]
    if command == "player":
        args += ["--name", "test star"]
    if command == "team":
        args += ["--team", "BOS"]
    assert main(args) == 0
    result = pd.read_csv(out)
    assert len(result) == (1 if command == "player" else 2)
    assert set(result.Year) == {2022}
    assert result.Reliability.gt(0).all()


def test_missing_season_and_files(lahman: Path) -> None:
    source = LahmanSource(str(lahman))
    with pytest.raises(DataFetchError, match="no data for 2025"):
        source.season(2025, "batting")
    missing = LahmanSource(str(lahman / "missing"))
    with pytest.raises(DataFetchError, match="Expected Batting.csv"):
        missing.season(2021, "batting")


def test_no_match_and_team(lahman: Path) -> None:
    source = LahmanSource(str(lahman))
    with pytest.raises(PlayerLookupError, match="No qualified"):
        source.project("player", 2022, "batting", name="Nobody Here")
    with pytest.raises(ProjectionError, match="team ID"):
        source.project("team", 2022, "batting", team="INVALID")


def test_duplicate_names_are_not_merged(lahman: Path) -> None:
    path = lahman / "People.csv"
    people = pd.read_csv(path)
    people.loc[people.playerID == "other", ["nameFirst", "nameLast"]] = ["Test", "Star"]
    people.to_csv(path, index=False)
    source = LahmanSource(str(lahman))
    assert len(source.project("batch", 2022, "batting")) == 2
    with pytest.raises(PlayerLookupError, match="Ambiguous"):
        source.project("player", 2022, "batting", name="Test Star")


@pytest.mark.parametrize(
    "case, message",
    [
        ("columns", "missing columns"),
        ("numeric", "Invalid numeric"),
        ("games", "no valid game counts"),
        ("empty", "No qualified"),
        ("duplicate", "Duplicate player IDs"),
        ("people", "missing players"),
    ],
)
def test_invalid_data_reports_actionable_errors(lahman: Path, case: str, message: str) -> None:
    if case in {"columns", "numeric", "empty"}:
        path = lahman / "Batting.csv"
        frame = pd.read_csv(path)
        if case == "columns":
            frame = frame.drop(columns="AB")
        elif case == "numeric":
            frame["AB"] = "invalid"
        else:
            frame[["AB", "BB", "HBP", "SF", "SH"]] = 0
    elif case == "games":
        path = lahman / "Teams.csv"
        frame = pd.read_csv(path)
        frame["G"] = 0
    else:
        path = lahman / "People.csv"
        frame = pd.read_csv(path)
        frame = pd.concat([frame, frame.iloc[[0]]]) if case == "duplicate" else frame.iloc[0:0]
    frame.to_csv(path, index=False)
    source = LahmanSource(str(lahman))
    with pytest.raises(DataFetchError, match=message):
        source.season(2021, "batting")


def test_unreadable_csv(lahman: Path) -> None:
    (lahman / "Batting.csv").write_text("", encoding="utf-8")
    source = LahmanSource(str(lahman))
    with pytest.raises(DataFetchError, match="Unable to read"):
        source.season(2021, "batting")


def test_optional_columns_and_case_insensitive_filenames(lahman: Path) -> None:
    path = lahman / "Batting.csv"
    pd.read_csv(path).drop(columns=["HBP", "SF", "SH"]).to_csv(lahman / "batting.csv", index=False)
    path.unlink()
    season = LahmanSource(str(lahman)).season(2021, "batting")
    assert (season[["HBP", "SF", "SH"]] == 0).all().all()


def test_invalid_kind(lahman: Path) -> None:
    source = LahmanSource(str(lahman))
    with pytest.raises(DataFetchError, match="Invalid kind"):
        source.season(2021, "fielding")


def test_cli_missing_directory_returns_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["batch", "--year", "2022", "--kind", "batting", "--data-dir", str(tmp_path)]) == 2
    assert "Expected Batting.csv" in capsys.readouterr().err


def test_qualification_boundary(lahman: Path) -> None:
    path = lahman / "Batting.csv"
    frame = pd.read_csv(path)
    frame.loc[frame.playerID == "star", ["AB", "BB", "HBP", "SF", "SH"]] = [502, 0, 0, 0, 0]
    frame.loc[frame.playerID == "other", ["AB", "BB", "HBP", "SF", "SH"]] = [501, 0, 0, 0, 0]
    frame.to_csv(path, index=False)
    assert set(LahmanSource(str(lahman)).season(2021, "batting").PlayerID) == {"star"}
    path = lahman / "Pitching.csv"
    frame = pd.read_csv(path)
    frame.loc[frame.playerID == "star", "IPouts"] = 486
    frame.loc[frame.playerID == "other", "IPouts"] = 485
    frame.to_csv(path, index=False)
    assert set(LahmanSource(str(lahman)).season(2021, "pitching").PlayerID) == {"star"}


def test_default_command_uses_local_files(
    lahman: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("local command attempted network access")

    monkeypatch.setattr("socket.create_connection", forbidden)
    monkeypatch.setattr("socket.socket.connect", forbidden)
    monkeypatch.setenv("LAHMAN_DATA_DIR", str(lahman))
    assert main(["player", "--name", "Test Star", "--year", "2022", "--kind", "batting"]) == 0
    assert "Test Star" in capsys.readouterr().out


def test_missing_default_files_never_fall_back_to_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("missing data triggered network fallback")

    monkeypatch.setattr("socket.socket.connect", forbidden)
    monkeypatch.setenv("LAHMAN_DATA_DIR", str(tmp_path))
    assert main(["player", "--name", "Test Star", "--year", "2022", "--kind", "batting"]) == 2
    assert "Expected Batting.csv" in capsys.readouterr().err
