import types
from pathlib import Path

import pandas as pd
import pytest

from marcelball import data
from marcelball.data import DataFetchError, PlayerLookupError


def test_candidate_full_names_with_first_last() -> None:
    row = pd.Series({"name_first": "  Juan ", "name_last": " Soto "})
    assert data._candidate_full_names(row) == {"juan soto"}


def test_candidate_full_names_with_name_given() -> None:
    row = pd.Series({"name_given": " Juan José Soto "})
    assert data._candidate_full_names(row) == {"juan josé soto"}


def test_candidate_full_names_with_missing_or_nan_names() -> None:
    row = pd.Series({"name_first": None, "name_last": float("nan"), "name_given": pd.NA})
    assert data._candidate_full_names(row) == set()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("", None),
        ("42", 42),
        ("nope", None),
        (object(), None),
    ],
)
def test_to_int_or_none(value: object, expected: int | None) -> None:
    assert data._to_int_or_none(value) == expected


def test_format_numeric_or_unknown_with_numeric_and_unknown_values() -> None:
    assert data._format_numeric_or_unknown("7") == "7"
    assert data._format_numeric_or_unknown("bad") == "?"


@pytest.mark.parametrize(
    ("row", "start", "end", "expected"),
    [
        ({"mlb_played_first": None, "mlb_played_last": None}, 2020, 2022, True),
        ({"mlb_played_first": None, "mlb_played_last": 2021}, 2020, 2022, True),
        ({"mlb_played_first": None, "mlb_played_last": 2019}, 2020, 2022, False),
        ({"mlb_played_first": 2021, "mlb_played_last": None}, 2020, 2022, True),
        ({"mlb_played_first": 2023, "mlb_played_last": None}, 2020, 2022, False),
        ({"mlb_played_first": 2010, "mlb_played_last": 2015}, 2020, 2022, False),
        ({"mlb_played_first": 2024, "mlb_played_last": 2025}, 2020, 2022, False),
        ({"mlb_played_first": 2020, "mlb_played_last": 2022}, 2020, 2022, True),
    ],
)
def test_overlaps_year_window_every_branch(
    row: dict[str, object], start: int, end: int, expected: bool
) -> None:
    assert data._overlaps_year_window(pd.Series(row), start, end) is expected


def test_filter_candidates_by_years_with_no_years() -> None:
    candidates = pd.DataFrame([{"key_fangraphs": 1}])
    filtered = data._filter_candidates_by_years(candidates, [])
    pd.testing.assert_frame_equal(filtered, candidates)


def test_filter_candidates_by_years_with_missing_year_columns() -> None:
    candidates = pd.DataFrame([{"key_fangraphs": 1}])
    filtered = data._filter_candidates_by_years(candidates, [2020])
    pd.testing.assert_frame_equal(filtered, candidates)


def test_filter_candidates_by_years_with_matching_window() -> None:
    candidates = pd.DataFrame(
        [
            {"key_fangraphs": 1, "mlb_played_first": 2018, "mlb_played_last": 2022},
            {"key_fangraphs": 2, "mlb_played_first": 1980, "mlb_played_last": 1985},
        ]
    )
    filtered = data._filter_candidates_by_years(candidates, [2020, 2021])
    assert list(filtered["key_fangraphs"]) == [1]


def test_filter_candidates_by_years_with_no_matching_window_returns_original() -> None:
    candidates = pd.DataFrame(
        [
            {"key_fangraphs": 1, "mlb_played_first": 1980, "mlb_played_last": 1985},
            {"key_fangraphs": 2, "mlb_played_first": 1990, "mlb_played_last": 1992},
        ]
    )
    filtered = data._filter_candidates_by_years(candidates, [2020, 2021])
    pd.testing.assert_frame_equal(filtered, candidates)


def test_resolve_player_lookup_with_empty_lookup() -> None:
    with pytest.raises(PlayerLookupError, match="No player found"):
        data.resolve_player_lookup("Any Name", pd.DataFrame(), [2020])


def test_resolve_player_lookup_with_one_candidate() -> None:
    lookup = pd.DataFrame([{"name_first": "Mike", "name_last": "Trout", "key_fangraphs": 101}])
    resolved = data.resolve_player_lookup("Mike Trout", lookup, [2020])
    assert int(resolved["key_fangraphs"]) == 101


def test_resolve_player_lookup_with_duplicates() -> None:
    lookup = pd.DataFrame(
        [
            {"name_first": "Mike", "name_last": "Trout", "key_fangraphs": 101},
            {"name_first": "Mike", "name_last": "Trout", "key_fangraphs": 102},
        ]
    )
    with pytest.raises(PlayerLookupError, match="Duplicate player match"):
        data.resolve_player_lookup("Mike Trout", lookup, [2020])


def test_resolve_player_lookup_with_no_candidate_in_target_seasons() -> None:
    lookup = pd.DataFrame(
        [
            {
                "name_first": "Mike",
                "name_last": "Trout",
                "key_fangraphs": 101,
                "mlb_played_first": 1990,
                "mlb_played_last": 1995,
            }
        ]
    )
    # no overlap -> year filter returns original candidates, so this resolves to only candidate
    resolved = data.resolve_player_lookup("Mike Trout", lookup, [2020, 2021])
    assert int(resolved["key_fangraphs"]) == 101


def test_cache_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(data, "CACHE_ROOT", tmp_path)
    path = data._cache_path("batting", 2025, "csv")
    assert path == tmp_path / "batting_2025.csv"
    assert tmp_path.exists()


def test_read_cache_parquet_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(data, "CACHE_ROOT", tmp_path)
    expected = pd.DataFrame([{"a": 1}])
    parquet_path = data._cache_path("batting", 2025, "parquet")
    parquet_path.write_text("placeholder", encoding="utf-8")
    monkeypatch.setattr(pd, "read_parquet", lambda _: expected)
    got = data._read_cache("batting", 2025)
    pd.testing.assert_frame_equal(got, expected)


def test_read_cache_csv_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(data, "CACHE_ROOT", tmp_path)
    expected = pd.DataFrame([{"a": 2}])
    csv_path = data._cache_path("pitching", 2024, "csv")
    csv_path.write_text("a\n2\n", encoding="utf-8")
    monkeypatch.setattr(pd, "read_csv", lambda _: expected)
    got = data._read_cache("pitching", 2024)
    pd.testing.assert_frame_equal(got, expected)


def test_read_cache_no_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(data, "CACHE_ROOT", tmp_path)
    assert data._read_cache("batting", 2030) is None


def test_write_cache_parquet_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(data, "CACHE_ROOT", tmp_path)
    called = {"parquet": False, "csv": False}

    def fake_to_parquet(self: pd.DataFrame, path: Path, index: bool = False) -> None:
        called["parquet"] = True

    def fake_to_csv(self: pd.DataFrame, path: Path, index: bool = False) -> None:
        called["csv"] = True

    monkeypatch.setattr(pd.DataFrame, "to_parquet", fake_to_parquet)
    monkeypatch.setattr(pd.DataFrame, "to_csv", fake_to_csv)

    data._write_cache("batting", 2025, pd.DataFrame([{"a": 1}]))
    assert called == {"parquet": True, "csv": False}


def test_write_cache_csv_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(data, "CACHE_ROOT", tmp_path)
    called = {"csv": False}

    def fail_to_parquet(self: pd.DataFrame, path: Path, index: bool = False) -> None:
        raise RuntimeError("boom")

    def fake_to_csv(self: pd.DataFrame, path: Path, index: bool = False) -> None:
        called["csv"] = True

    monkeypatch.setattr(pd.DataFrame, "to_parquet", fail_to_parquet)
    monkeypatch.setattr(pd.DataFrame, "to_csv", fake_to_csv)

    data._write_cache("pitching", 2025, pd.DataFrame([{"a": 1}]))
    assert called["csv"] is True


def test_fetch_season_stats_cache_hit(monkeypatch: pytest.MonkeyPatch) -> None:
    cached = pd.DataFrame([{"a": 1}])
    monkeypatch.setattr(data, "_read_cache", lambda kind, year: cached)
    got = data.fetch_season_stats(2025, "batting", use_cache=True)
    pd.testing.assert_frame_equal(got, cached)


def test_fetch_season_stats_batting_fetch_success(monkeypatch: pytest.MonkeyPatch) -> None:
    df = pd.DataFrame([{"a": 1}])
    monkeypatch.setattr(data, "_read_cache", lambda kind, year: None)
    monkeypatch.setattr(data, "_write_cache", lambda kind, year, frame: None)
    fake_pyb = types.SimpleNamespace(
        batting_stats=lambda year: df,
        pitching_stats=lambda year: pd.DataFrame([{"a": 9}]),
    )
    monkeypatch.setitem(__import__("sys").modules, "pybaseball", fake_pyb)

    got = data.fetch_season_stats(2025, "batting", use_cache=False)
    pd.testing.assert_frame_equal(got, df)


def test_fetch_season_stats_pitching_fetch_success(monkeypatch: pytest.MonkeyPatch) -> None:
    df = pd.DataFrame([{"a": 2}])
    monkeypatch.setattr(data, "_read_cache", lambda kind, year: None)
    monkeypatch.setattr(data, "_write_cache", lambda kind, year, frame: None)
    fake_pyb = types.SimpleNamespace(
        batting_stats=lambda year: pd.DataFrame([{"a": 9}]),
        pitching_stats=lambda year: df,
    )
    monkeypatch.setitem(__import__("sys").modules, "pybaseball", fake_pyb)

    got = data.fetch_season_stats(2025, "pitching", use_cache=False)
    pd.testing.assert_frame_equal(got, df)


def test_fetch_season_stats_pybaseball_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(data, "_read_cache", lambda kind, year: None)
    fake_pyb = types.SimpleNamespace(
        batting_stats=lambda year: (_ for _ in ()).throw(RuntimeError("down")),
        pitching_stats=lambda year: pd.DataFrame([{"a": 9}]),
    )
    monkeypatch.setitem(__import__("sys").modules, "pybaseball", fake_pyb)

    with pytest.raises(DataFetchError, match="Unable to fetch batting stats"):
        data.fetch_season_stats(2025, "batting", use_cache=False)


def test_fetch_season_stats_empty_dataframe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(data, "_read_cache", lambda kind, year: None)
    fake_pyb = types.SimpleNamespace(
        batting_stats=lambda year: pd.DataFrame(),
        pitching_stats=lambda year: pd.DataFrame([{"a": 9}]),
    )
    monkeypatch.setitem(__import__("sys").modules, "pybaseball", fake_pyb)

    with pytest.raises(DataFetchError, match="No batting stats returned"):
        data.fetch_season_stats(2025, "batting", use_cache=False)


def test_lookup_player_ids_first_last_validation() -> None:
    with pytest.raises(PlayerLookupError, match="Provide both first and last name"):
        data.lookup_player_ids("Madonna")


def test_lookup_player_ids_success(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = pd.DataFrame([{"key_fangraphs": 123}])
    fake_pyb = types.SimpleNamespace(playerid_lookup=lambda last, first: expected)
    monkeypatch.setitem(__import__("sys").modules, "pybaseball", fake_pyb)

    got = data.lookup_player_ids("Mike Trout")
    pd.testing.assert_frame_equal(got, expected)


def test_lookup_player_ids_pybaseball_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_pyb = types.SimpleNamespace(
        playerid_lookup=lambda last, first: (_ for _ in ()).throw(RuntimeError("network"))
    )
    monkeypatch.setitem(__import__("sys").modules, "pybaseball", fake_pyb)

    with pytest.raises(PlayerLookupError, match="Failed player lookup"):
        data.lookup_player_ids("Mike Trout")


def test_lookup_player_ids_empty_result(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_pyb = types.SimpleNamespace(playerid_lookup=lambda last, first: pd.DataFrame())
    monkeypatch.setitem(__import__("sys").modules, "pybaseball", fake_pyb)

    with pytest.raises(PlayerLookupError, match="No player found"):
        data.lookup_player_ids("Mike Trout")
