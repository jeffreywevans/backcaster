from pathlib import Path

import pandas as pd
import pytest

from backcaster.cli import main
from backcaster.data import DataLoadError, PlayerLookupError
from backcaster.lahman import LahmanSource
from backcaster.marcel import ProjectionError


@pytest.fixture
def lahman(tmp_path: Path) -> Path:
    pd.DataFrame(
        [
            {"playerID": "star", "nameFirst": "Test", "nameLast": "Star", "birthYear": 1990},
            {"playerID": "other", "nameFirst": "Other", "nameLast": "Player", "birthYear": 1993},
            {"playerID": "minor", "nameFirst": "Brief", "nameLast": "Career", "birthYear": 1995},
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
                    H=150 if player != "minor" else 5,
                    **{"2B": 30 if player != "minor" else 1, "3B": 2 if player != "minor" else 0},
                    HR=20 if player != "minor" else 0,
                    BB=bb,
                    SO=100 if player != "minor" else 5,
                    R=80 if player != "minor" else 2,
                    RBI=75 if player != "minor" else 2,
                    SB=10 if player != "minor" else 1,
                    CS=3 if player != "minor" else 0,
                    IBB=4 if player != "minor" else 0,
                    GIDP=10 if player != "minor" else 1,
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
                    W=10,
                    L=8,
                    SV=0,
                    R=65,
                    IBB=3,
                    HBP=4,
                    BK=1,
                    WP=2,
                    ER=60,
                    H=150,
                    HR=20,
                    BB=50,
                    SO=180,
                    BFP=700,
                )
            )
    pd.DataFrame(
        [
            dict(playerID=p, yearID=y, G_all=100, G_p=0)
            for p in ["star", "other", "minor"]
            for y in (2019, 2020, 2021)
        ]
    ).to_csv(tmp_path / "Appearances.csv", index=False)
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
    for column in [
        "AB",
        "H",
        "2B",
        "3B",
        "HR",
        "BB",
        "SO",
        "HBP",
        "SF",
        "SH",
        "R",
        "RBI",
        "SB",
        "CS",
        "IBB",
        "GIDP",
    ]:
        row[column] = row[column] / 2
    second = row.assign(stint=2, teamID="LAN")
    pd.concat([frame, row, second]).to_csv(path, index=False)
    season = LahmanSource(str(lahman)).season(2021, "batting")
    star = season[season.PlayerID == "star"]
    assert len(star) == 1
    assert star.iloc[0]["PA"] == 571
    assert star.iloc[0]["R"] == 80
    assert star.iloc[0]["RBI"] == 75
    assert star.iloc[0]["SB"] == 10
    assert star.iloc[0]["CS"] == 3
    assert star.iloc[0]["IBB"] == 4
    assert star.iloc[0]["GDP"] == 10
    assert star.iloc[0]["Team"] == "LAN"


def test_short_season_threshold(lahman: Path) -> None:
    path = lahman / "Batting.csv"
    frame = pd.read_csv(path)
    frame.loc[frame.playerID == "star", ["AB", "BB", "HBP", "SF", "SH"]] = [190, 0, 0, 0, 0]
    frame.loc[frame.playerID == "star", ["H", "SO", "IBB"]] = [60, 20, 0]
    frame.to_csv(path, index=False)
    source = LahmanSource(str(lahman))
    assert "star" in set(source.season(2020, "batting").PlayerID)
    assert "star" not in set(source.season(2021, "batting").PlayerID)
    result = source.project("player", 2022, "batting", name="Test Star")
    assert result.loc[0, "PA"] == pytest.approx(0.5 * 190 + 0.1 * 190 + 200)


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
    with pytest.raises(DataLoadError, match="no data for 2025"):
        source.season(2025, "batting")
    missing = LahmanSource(str(lahman / "missing"))
    with pytest.raises(DataLoadError, match="Expected Batting.csv"):
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
    with pytest.raises(DataLoadError, match=message):
        source.season(2021, "batting")


def test_unreadable_csv(lahman: Path) -> None:
    (lahman / "Batting.csv").write_text("", encoding="utf-8")
    source = LahmanSource(str(lahman))
    with pytest.raises(DataLoadError, match="Unable to read"):
        source.season(2021, "batting")


def test_optional_columns_and_case_insensitive_filenames(lahman: Path) -> None:
    path = lahman / "Batting.csv"
    pd.read_csv(path).drop(columns=["HBP", "SF", "SH"]).to_csv(lahman / "batting.csv", index=False)
    path.unlink()
    season = LahmanSource(str(lahman)).season(2021, "batting")
    assert (season[["HBP", "SF", "SH"]] == 0).all().all()


def test_invalid_kind(lahman: Path) -> None:
    source = LahmanSource(str(lahman))
    with pytest.raises(DataLoadError, match="Invalid kind"):
        source.season(2021, "fielding")


def test_cli_missing_directory_returns_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["batch", "--year", "2022", "--kind", "batting", "--data-dir", str(tmp_path)]) == 2
    assert "Expected People.csv" in capsys.readouterr().err


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
    assert "Expected People.csv" in capsys.readouterr().err


def test_batter_commands_share_population_rebaseline(lahman: Path) -> None:
    source = LahmanSource(str(lahman))
    player = source.project("player", 2022, "batting", name="Test Star")
    batch = source.project("batch", 2022, "batting")
    team = source.project("team", 2022, "batting", team="BOS")
    expected = batch[batch.PlayerID == "star"].reset_index(drop=True)
    pd.testing.assert_frame_equal(player, expected)
    pd.testing.assert_frame_equal(team, batch)
    assert player.loc[0, "PA"] == pytest.approx(0.5 * 571 + 0.1 * 571 + 200)
    assert player.loc[0, "Age"] == 32


def test_pitcher_exclusion_and_unqualified_league_context(lahman: Path) -> None:
    source = LahmanSource(str(lahman))
    before = source.project("batch", 2022, "batting")
    path = lahman / "Appearances.csv"
    appearances = pd.read_csv(path)
    appearances.loc[appearances.playerID == "minor", "G_p"] = 100
    appearances.to_csv(path, index=False)
    after = LahmanSource(str(lahman)).project("batch", 2022, "batting")
    assert set(after.PlayerID) == {"star", "other"}
    assert not before.HR.equals(after.HR)


@pytest.mark.parametrize(
    "case, message",
    [
        ("missing", "must cover"),
        ("numeric", "Invalid game counts"),
        ("no_qualified", "No qualified non-pitcher"),
    ],
)
def test_batting_population_errors(lahman: Path, case: str, message: str) -> None:
    path = lahman / "Appearances.csv"
    frame = pd.read_csv(path)
    if case == "missing":
        frame = frame[frame.playerID != "star"]
    elif case == "numeric":
        frame["G_p"] = "invalid"
    else:
        # Only the unqualified player remains a non-pitcher.
        frame.loc[frame.playerID != "minor", "G_p"] = 100
    frame.to_csv(path, index=False)
    source = LahmanSource(str(lahman))
    with pytest.raises((DataLoadError, ProjectionError), match=message):
        source.project("batch", 2022, "batting")


@pytest.mark.parametrize("bad", [-1, 101, float("inf"), float("nan")])
def test_invalid_appearance_counts(lahman: Path, bad: float) -> None:
    path = lahman / "Appearances.csv"
    frame = pd.read_csv(path)
    frame["G_p"] = bad
    frame.to_csv(path, index=False)
    source = LahmanSource(str(lahman))
    with pytest.raises(DataLoadError, match="Invalid game counts"):
        source.project("batch", 2022, "batting")


def test_missing_birth_year_column(lahman: Path) -> None:
    path = lahman / "People.csv"
    pd.read_csv(path).drop(columns="birthYear").to_csv(path, index=False)
    source = LahmanSource(str(lahman))
    with pytest.raises(DataLoadError, match="birthYear"):
        source.project("batch", 2022, "batting")


def test_pitcher_aging_consistent_across_commands(lahman: Path) -> None:
    source = LahmanSource(str(lahman))
    player = source.project("player", 2022, "pitching", name="Test Star").iloc[0]
    team = source.project("team", 2022, "pitching", team="BOS")
    batch = source.project("batch", 2022, "pitching")
    assert player["Age"] == 32
    assert player["IP"] == pytest.approx(487 / 3)
    for result in [team, batch]:
        row = result[result.Name == "Test Star"].iloc[0]
        for stat in ["IP", "SO", "ERA", "WHIP", "Age"]:
            assert row[stat] == pytest.approx(player[stat])


def test_pitcher_requires_birth_year(lahman: Path) -> None:
    path = lahman / "People.csv"
    pd.read_csv(path).drop(columns="birthYear").to_csv(path, index=False)
    source = LahmanSource(str(lahman))
    with pytest.raises(DataLoadError, match="birthYear"):
        source.project("batch", 2022, "pitching")


@pytest.mark.parametrize("command, kind", [("hitters", "batting"), ("pitchers", "pitching")])
def test_league_commands_match_batch(lahman: Path, command: str, kind: str) -> None:
    out = lahman / f"{command}.csv"
    batch = lahman / "batch.csv"
    common = ["--year", "2022", "--data-dir", str(lahman), "--format", "csv"]
    assert main([command, *common, "--out", str(out)]) == 0
    assert main(["batch", *common, "--kind", kind, "--out", str(batch)]) == 0
    pd.testing.assert_frame_equal(pd.read_csv(out), pd.read_csv(batch))
    assert len(pd.read_csv(out)) == 2


def test_pitcher_full_history_survives_team_and_qualification_selection(lahman: Path) -> None:
    path = lahman / "Pitching.csv"
    frame = pd.read_csv(path)
    frame.loc[(frame.playerID == "star") & (frame.yearID == 2019), "teamID"] = "LAN"
    middle = (frame.playerID == "star") & (frame.yearID == 2020)
    frame.loc[middle, ["teamID", "IPouts", "ER"]] = ["LAA", 90, 20]
    frame.to_csv(path, index=False)
    source = LahmanSource(str(lahman))
    player = source.project("player", 2022, "pitching", name="Test Star").iloc[0]
    team = source.project("team", 2022, "pitching", team="LAN").iloc[0]
    batch = source.project("batch", 2022, "pitching")
    row = batch[batch.Name == "Test Star"].iloc[0]
    assert player["IP"] == pytest.approx((5 * 487 / 3 + 4 * 30 + 3 * 487 / 3) / 12)
    for candidate in [team, row]:
        for metric in ["IP", "ER", "ERA", "WHIP", "SO", "Reliability"]:
            assert candidate[metric] == pytest.approx(player[metric])


def test_pitcher_trade_stints_count_once_and_qualify_together(lahman: Path) -> None:
    original = LahmanSource(str(lahman)).project("batch", 2022, "pitching")
    path = lahman / "Pitching.csv"
    frame = pd.read_csv(path)
    mask = (frame.playerID == "star") & (frame.yearID == 2021)
    row = frame[mask].copy()
    frame = frame[~mask]
    for column in [
        "IPouts",
        "ER",
        "H",
        "HR",
        "BB",
        "SO",
        "BFP",
        "W",
        "L",
        "SV",
        "R",
        "IBB",
        "HBP",
        "BK",
        "WP",
    ]:
        row[column] = row[column] / 2
    second = row.assign(stint=2, teamID="LAN")
    pd.concat([frame, row, second]).to_csv(path, index=False)
    source = LahmanSource(str(lahman))
    season = source.season(2021, "pitching")
    assert len(season[season.PlayerID == "star"]) == 1
    actual = source.project("batch", 2022, "pitching")
    pd.testing.assert_frame_equal(
        actual.sort_values("PlayerID").reset_index(drop=True),
        original.sort_values("PlayerID").reset_index(drop=True),
    )


def test_pitcher_without_three_qualifying_seasons_can_be_selected(lahman: Path) -> None:
    path = lahman / "Pitching.csv"
    frame = pd.read_csv(path)
    frame.loc[(frame.playerID == "star") & (frame.yearID != 2021), "IPouts"] = 90
    frame.to_csv(path, index=False)
    result = LahmanSource(str(lahman)).project("player", 2022, "pitching", name="Test Star")
    assert len(result) == 1
    assert result.loc[0, "IP"] == pytest.approx((5 * 487 / 3 + 4 * 30 + 3 * 30) / 12)


@pytest.mark.parametrize(
    "kind, schema",
    [
        ("batting", "PA,AB,R,H,2B,3B,HR,RBI,SB,CS,BB,SO,BA,OBP,SLG,OPS,TB,GDP,HBP,SH,SF,IBB"),
        (
            "pitching",
            "W,L,W-L%,ERA,SV,IP,H,R,ER,HR,BB,IBB,SO,HBP,BK,WP,BF,WHIP,H9,HR9,BB9,SO9,SO/W",
        ),
    ],
)
def test_full_schema_in_cli_and_csv(lahman: Path, kind: str, schema: str) -> None:
    from backcaster.outputs import to_cli_table, to_csv

    frame = LahmanSource(str(lahman)).project("batch", 2022, kind)
    expected = ["Name", "Year", "PlayerID", "Age", *schema.split(","), "Reliability"]
    out = to_csv(frame, lahman / "schema.csv")
    assert pd.read_csv(out).columns.tolist() == expected
    assert to_cli_table(frame).splitlines()[0].split() == expected


@pytest.mark.parametrize("kind", ["batting", "pitching"])
def test_duplicate_name_selected_by_id(
    lahman: Path, kind: str, capsys: pytest.CaptureFixture[str]
) -> None:
    path = lahman / "People.csv"
    people = pd.read_csv(path)
    people.loc[people.playerID.isin(["star", "other"]), ["nameFirst", "nameLast"]] = [
        "Chris",
        "Young",
    ]
    people.to_csv(path, index=False)
    source = LahmanSource(str(lahman))
    batch = source.project("batch", 2022, kind).set_index("PlayerID")
    with pytest.raises(PlayerLookupError, match="--player-id"):
        source.project("player", 2022, kind, name="Chris Young")
    for player_id in ["star", "other"]:
        result = source.project("player", 2022, kind, player_id=player_id).set_index("PlayerID")
        pd.testing.assert_frame_equal(result, batch.loc[[player_id]])
        assert (
            main(
                [
                    "player",
                    "--player-id",
                    player_id,
                    "--year",
                    "2022",
                    "--kind",
                    kind,
                    "--data-dir",
                    str(lahman),
                ]
            )
            == 0
        )
        output = capsys.readouterr().out
        assert player_id in output
        assert "Chris Young" in output


@pytest.mark.parametrize("kind", ["batting", "pitching"])
@pytest.mark.parametrize("player_id", ["unknown", "minor"])
def test_player_id_lookup_preserves_eligibility(
    lahman: Path, kind: str, player_id: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        main(
            [
                "player",
                "--player-id",
                player_id,
                "--year",
                "2022",
                "--kind",
                kind,
                "--data-dir",
                str(lahman),
            ]
        )
        == 2
    )
    assert (
        f"No qualified Lahman player found for player ID '{player_id}'" in capsys.readouterr().err
    )


def test_project_rejects_name_and_player_id(lahman: Path) -> None:
    with pytest.raises(ValueError, match="either name or player_id"):
        LahmanSource(str(lahman)).project(
            "player", 2022, "batting", name="Test Star", player_id="star"
        )


def test_csv_reads_select_columns_and_reuse_people_lookup(
    lahman: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = LahmanSource(str(lahman)).project("batch", 2022, "batting")
    for name in ["Batting", "Pitching", "People", "Teams", "Appearances"]:
        path = lahman / f"{name}.csv"
        frame = pd.read_csv(path)
        frame["UnusedLargeText"] = "x" * 10000
        frame.to_csv(path, index=False)
    read_csv = pd.read_csv
    reads: list[str] = []

    def selected_read(path, **kwargs):
        assert callable(kwargs["usecols"])
        assert not kwargs["usecols"]("UnusedLargeText")
        reads.append(path.stem)
        return read_csv(path, **kwargs)

    monkeypatch.setattr(pd, "read_csv", selected_read)
    source = LahmanSource(str(lahman))
    actual = source.project("batch", 2022, "batting")
    pd.testing.assert_frame_equal(actual, expected)
    people_lookup = source._people
    source.project("batch", 2022, "pitching")
    assert source._people is people_lookup
    assert sorted(reads) == ["Appearances", "Batting", "People", "Pitching", "Teams"]
    assert all("UnusedLargeText" not in table for table in source.tables.values())


def test_read_expands_cached_column_selection(lahman: Path) -> None:
    source = LahmanSource(str(lahman))
    assert source.read("Teams", {"yearID"}).columns.tolist() == ["yearID"]
    expanded = source.read("Teams", {"G"})
    assert set(expanded) == {"yearID", "G"}
    with pytest.raises(DataLoadError, match="missing columns: absent"):
        source.read("Teams", {"absent"})


def test_season_names_without_optional_birth_year(lahman: Path) -> None:
    path = lahman / "People.csv"
    people = pd.read_csv(path).drop(columns="birthYear")
    people.loc[people.playerID == "star", "nameFirst"] = None
    people.to_csv(path, index=False)
    season = LahmanSource(str(lahman)).season(2021, "batting")
    assert season.loc[season.PlayerID == "star", "Name"].iloc[0] == "Star"
    assert "birthYear" not in season
