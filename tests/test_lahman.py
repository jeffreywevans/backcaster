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
    assert len(result) == (1 if command == "player" else (3 if kind == "batting" else 2))
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
    with pytest.raises(PlayerLookupError, match="No eligible"):
        source.project("player", 2022, "batting", name="Nobody Here")
    with pytest.raises(ProjectionError, match="team ID"):
        source.project("team", 2022, "batting", team="INVALID")


def test_duplicate_names_are_not_merged(lahman: Path) -> None:
    path = lahman / "People.csv"
    people = pd.read_csv(path)
    people.loc[people.playerID == "other", ["nameFirst", "nameLast"]] = ["Test", "Star"]
    people.to_csv(path, index=False)
    source = LahmanSource(str(lahman))
    assert len(source.project("batch", 2022, "batting")) == 3
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
        ("all_pitchers", "No non-pitcher batting history"),
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
        # No non-pitcher history remains.
        frame["G_p"] = 100
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
    assert player["IP"] == pytest.approx(0.6 * 487 / 3 + 60)
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
    assert len(pd.read_csv(out)) == (3 if kind == "batting" else 2)


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
    assert player["IP"] == pytest.approx(0.5 * 487 / 3 + 0.1 * 30 + 60)
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
    assert result.loc[0, "IP"] == pytest.approx(0.5 * 487 / 3 + 0.1 * 30 + 60)


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
    if kind == "batting":
        expected.append("ConfidenceTier")
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


@pytest.mark.parametrize(
    "kind, player_id, expected",
    [
        ("batting", "unknown", 2),
        ("pitching", "unknown", 2),
        ("batting", "minor", 0),
        ("pitching", "minor", 2),
    ],
)
def test_player_id_lookup_preserves_eligibility(
    lahman: Path, kind: str, player_id: str, expected: int, capsys: pytest.CaptureFixture[str]
) -> None:
    result = main(
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
    assert result == expected
    captured = capsys.readouterr()
    if expected == 2:
        assert f"No eligible Lahman player found for player ID '{player_id}'" in captured.err
    else:
        assert "low-sample" in captured.out


def test_project_rejects_name_and_player_id(lahman: Path) -> None:
    source = LahmanSource(str(lahman))
    with pytest.raises(ValueError, match="either name or player_id"):
        source.project("player", 2022, "batting", name="Test Star", player_id="star")


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


def test_pitcher_with_only_old_qualified_season_has_decayed_playing_time(lahman: Path) -> None:
    path = lahman / "Pitching.csv"
    history = pd.read_csv(path)
    history = history[~((history.playerID == "star") & (history.yearID != 2019))]
    history.to_csv(path, index=False)
    source = LahmanSource(str(lahman))
    for command, selection in [
        ("player", {"player_id": "star"}),
        ("team", {"team": "BOS"}),
        ("batch", {}),
    ]:
        result = source.project(command, 2022, "pitching", **selection)
        row = result[result.PlayerID == "star"].iloc[0]
        assert row.IP == pytest.approx(60.0)
        assert row.Reliability == pytest.approx(487 / (487 + 200))


@pytest.mark.parametrize(
    "kind, population", [("batting", "non-pitcher batters"), ("pitching", "pitchers")]
)
@pytest.mark.parametrize("player_id", ["minor", "star"])
@pytest.mark.parametrize("birth", [float("nan"), "unknown", float("inf"), 1800, 2021])
def test_missing_age_excludes_only_affected_players(
    lahman: Path,
    caplog: pytest.LogCaptureFixture,
    player_id: str,
    birth: object,
    kind: str,
    population: str,
) -> None:
    path = lahman / "People.csv"
    people = pd.read_csv(path)
    people["birthYear"] = people.birthYear.astype(object)
    people.loc[people.playerID == player_id, "birthYear"] = birth
    people.to_csv(path, index=False)
    source = LahmanSource(str(lahman))
    batch = source.project("batch", 2022, kind)
    assert set(batch.PlayerID) == (
        ({"star", "other", "minor"} if kind == "batting" else {"star", "other"}) - {player_id}
    )
    assert batch.Age.between(15, 70).all()
    assert f"Skipping 1 {population}" in caplog.text
    assert f"Player IDs: {player_id}" in caplog.text
    team = source.project("team", 2022, kind, team="BOS")
    pd.testing.assert_frame_equal(team, batch)
    selected = source.project("player", 2022, kind, player_id="other")
    pd.testing.assert_frame_equal(selected, batch[batch.PlayerID == "other"].reset_index(drop=True))
    if player_id == "star":
        with pytest.raises(PlayerLookupError, match="No eligible"):
            source.project("player", 2022, kind, player_id="star")


@pytest.mark.parametrize(
    "kind, population", [("batting", "non-pitcher batters"), ("pitching", "pitchers")]
)
def test_all_players_missing_birth_year_reports_actionable_error(
    lahman: Path, kind: str, population: str
) -> None:
    path = lahman / "People.csv"
    people = pd.read_csv(path)
    people["birthYear"] = float("nan")
    people.to_csv(path, index=False)
    source = LahmanSource(str(lahman))
    with pytest.raises(ProjectionError, match=f"No {population} with valid birthYear remain"):
        source.project("batch", 2022, kind)


@pytest.mark.parametrize("command, missing_id", [("hitters", "minor"), ("pitchers", "star")])
def test_1934_html_survives_unknown_birth_year(
    lahman: Path, caplog: pytest.LogCaptureFixture, command: str, missing_id: str
) -> None:
    for name in ["Batting", "Pitching", "Teams", "Appearances"]:
        path = lahman / f"{name}.csv"
        frame = pd.read_csv(path)
        frame["yearID"] -= 88
        frame.to_csv(path, index=False)
    path = lahman / "People.csv"
    people = pd.read_csv(path)
    people["birthYear"] -= 88
    people.loc[people.playerID == missing_id, "birthYear"] = float("nan")
    people.to_csv(path, index=False)
    output = lahman / f"{command}_1934.html"
    assert (
        main(
            [
                command,
                "--year",
                "1934",
                "--format",
                "html",
                "--out",
                str(output),
                "--data-dir",
                str(lahman),
            ]
        )
        == 0
    )
    html = output.read_text()
    assert "1934" in html
    assert ("Test Star" in html) == (missing_id != "star")
    assert "Other Player" in html
    assert "Brief Career" not in html
    assert "Skipping 1" in caplog.text


def test_batter_age_warning_bounds_long_player_list(
    lahman: Path, caplog: pytest.LogCaptureFixture
) -> None:
    for name in ["People", "Batting", "Appearances"]:
        path = lahman / f"{name}.csv"
        frame = pd.read_csv(path)
        template = frame[frame.playerID == "minor"]
        extra = pd.concat(
            [template.assign(playerID=f"missing{i}") for i in range(12)], ignore_index=True
        )
        if name == "People":
            extra["birthYear"] = float("nan")
        pd.concat([frame, extra], ignore_index=True).to_csv(path, index=False)
    result = LahmanSource(str(lahman)).project("batch", 2022, "batting")
    assert set(result.PlayerID) == {"star", "other", "minor"}
    assert "Skipping 12" in caplog.text
    assert "missing9, ..." in caplog.text
    assert "missing10" not in caplog.text


def test_three_pa_hitter_receives_projection_and_low_sample_label(lahman: Path) -> None:
    path = lahman / "Batting.csv"
    history = pd.read_csv(path)
    history = history[~((history.playerID == "minor") & (history.yearID != 2021))]
    counts = [c for c in history if c not in {"playerID", "yearID", "stint", "teamID"}]
    history.loc[history.playerID == "minor", counts] = 0
    history.loc[history.playerID == "minor", ["AB", "H", "SO"]] = [3, 1, 1]
    history.to_csv(path, index=False)
    source = LahmanSource(str(lahman))
    for command, selection in [
        ("player", {"player_id": "minor"}),
        ("team", {"team": "BOS"}),
        ("batch", {}),
    ]:
        result = source.project(command, 2022, "batting", **selection)
        row = result[result.PlayerID == "minor"].iloc[0]
        assert row.PA == pytest.approx(201.5)
        assert row.Reliability == pytest.approx(15 / 1215)
        assert row.ConfidenceTier == "low-sample"


def test_zero_pa_hitter_is_not_projected(lahman: Path) -> None:
    path = lahman / "Batting.csv"
    history = pd.read_csv(path)
    counts = [c for c in history if c not in {"playerID", "yearID", "stint", "teamID"}]
    history.loc[history.playerID == "minor", counts] = 0
    history.to_csv(path, index=False)
    result = LahmanSource(str(lahman)).project("batch", 2022, "batting")
    assert set(result.PlayerID) == {"star", "other"}


def test_population_without_qualified_batters_still_projects(lahman: Path) -> None:
    path = lahman / "Appearances.csv"
    appearances = pd.read_csv(path)
    appearances.loc[appearances.playerID != "minor", "G_p"] = 100
    appearances.to_csv(path, index=False)
    result = LahmanSource(str(lahman)).project("batch", 2022, "batting")
    assert result.PlayerID.tolist() == ["minor"]
    assert result.ConfidenceTier.tolist() == ["low-sample"]


def test_dated_eligibility_selects_low_sample_player_without_changing_model(lahman: Path) -> None:
    source = LahmanSource(str(lahman))
    full = source.project("batch", 2022, "batting")
    snapshot = lahman / "eligibility.csv"
    pd.DataFrame(
        [
            dict(PlayerID="minor", Year=2022, AsOf="2022-01-14", Eligible="true", Team="NYY"),
            dict(PlayerID="star", Year=2022, AsOf="2022-01-14", Eligible="false", Team="BOS"),
            dict(PlayerID="other", Year=2022, AsOf="2022-02-01", Eligible="true", Team="BOS"),
            dict(PlayerID="no-history", Year=2022, AsOf="2022-01-14", Eligible="true", Team=""),
        ]
    ).to_csv(snapshot, index=False)
    for command, selection in [
        ("batch", {}),
        ("player", {"player_id": "minor"}),
        ("team", {"team": "NYY"}),
    ]:
        result = source.project(
            command, 2022, "batting", eligibility_file=snapshot, as_of="2022-01-14", **selection
        )
        assert result.EligibilityAsOf.tolist() == ["2022-01-14"]
        pd.testing.assert_frame_equal(
            result.drop(columns="EligibilityAsOf"),
            full[full.PlayerID == "minor"].reset_index(drop=True),
        )
    with pytest.raises(PlayerLookupError, match="No eligible"):
        source.project(
            "player",
            2022,
            "batting",
            player_id="star",
            eligibility_file=snapshot,
            as_of="2022-01-14",
        )
    later = source.project("batch", 2022, "batting", eligibility_file=snapshot, as_of="2022-02-01")
    assert later.PlayerID.tolist() == ["other"]
    with pytest.raises(ProjectionError, match="No eligible players"):
        source.project(
            "team", 2022, "batting", team="BOS", eligibility_file=snapshot, as_of="2022-01-14"
        )


def test_eligibility_snapshot_requires_team_for_team_selection(lahman: Path) -> None:
    path = lahman / "eligibility.csv"
    pd.DataFrame([dict(PlayerID="minor", Year=2022, AsOf="2022-01-14", Eligible="true")]).to_csv(
        path, index=False
    )
    source = LahmanSource(str(lahman))
    with pytest.raises(DataLoadError, match="requires a Team column"):
        source.project(
            "team", 2022, "batting", team="BOS", eligibility_file=path, as_of="2022-01-14"
        )


def test_cli_exports_all_confidence_tiers_and_snapshot_date(lahman: Path) -> None:
    path = lahman / "eligibility.csv"
    pd.DataFrame(
        [
            dict(PlayerID=player, Year=2022, AsOf="2022-01-14", Eligible="true")
            for player in ["star", "minor"]
        ]
    ).to_csv(path, index=False)
    for fmt in ["csv", "html"]:
        out = lahman / f"eligible.{fmt}"
        assert (
            main(
                [
                    "hitters",
                    "--year",
                    "2022",
                    "--data-dir",
                    str(lahman),
                    "--eligibility-file",
                    str(path),
                    "--as-of",
                    "2022-01-14",
                    "--format",
                    fmt,
                    "--out",
                    str(out),
                ]
            )
            == 0
        )
        if fmt == "csv":
            result = pd.read_csv(out)
            assert set(result.PlayerID) == {"star", "minor"}
            assert set(result.ConfidenceTier) == {"core", "low-sample"}
            assert result.EligibilityAsOf.eq("2022-01-14").all()
        else:
            text = out.read_text()
            for value in ["<td>core</td>", "<td>low-sample</td>", "<td>2022-01-14</td>"]:
                assert value in text
