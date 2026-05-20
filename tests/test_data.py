import sys
import types
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import pytest

from backcaster import data
from backcaster.data import DataFetchError, PlayerLookupError


@pytest.fixture
def disable_cache_io(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(data, "_read_cache", lambda kind, year: None)
    monkeypatch.setattr(data, "_write_cache", lambda kind, year, frame: None)


def _install_fake_pybaseball(
    monkeypatch: pytest.MonkeyPatch, **attrs: object
) -> types.SimpleNamespace:
    fake_pyb = types.SimpleNamespace(**attrs)
    monkeypatch.setitem(sys.modules, "pybaseball", fake_pyb)
    return fake_pyb


@pytest.fixture
def install_fake_pybaseball(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[..., types.SimpleNamespace]:
    return lambda **attrs: _install_fake_pybaseball(monkeypatch, **attrs)


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
        (True, 1),
        (False, 0),
        ("42", 42),
        (" 42 ", 42),
        ("42.0", None),
        (42, 42),
        (42.5, 42),
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


def test_filter_candidates_by_years_with_no_matching_window_returns_empty() -> None:
    candidates = pd.DataFrame(
        [
            {"key_fangraphs": 1, "mlb_played_first": 1980, "mlb_played_last": 1985},
            {"key_fangraphs": 2, "mlb_played_first": 1990, "mlb_played_last": 1992},
        ]
    )
    filtered = data._filter_candidates_by_years(candidates, [2020, 2021])
    assert filtered.empty


def test_resolve_player_lookup_with_empty_lookup() -> None:
    with pytest.raises(PlayerLookupError, match=r"^No player found"):
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
    with pytest.raises(PlayerLookupError, match=r"^Duplicate player match"):
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
    with pytest.raises(PlayerLookupError, match=r"^No player found.*in seasons"):
        data.resolve_player_lookup("Mike Trout", lookup, [2020, 2021])


def test_cache_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(data, "CACHE_ROOT", tmp_path)
    path = data._cache_path("batting", 2025, "csv")
    assert path == tmp_path / "batting_2025.csv"
    assert tmp_path.exists()


def test_cache_path_rejects_invalid_kind(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(data, "CACHE_ROOT", tmp_path)
    with pytest.raises(ValueError, match=r"^Invalid kind"):
        data._cache_path("batting/../../evil", 2025, "csv")  # type: ignore[arg-type]


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




def test_read_cache_parquet_read_error_falls_back_to_csv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(data, "CACHE_ROOT", tmp_path)
    parquet_path = data._cache_path("batting", 2025, "parquet")
    parquet_path.write_text("placeholder", encoding="utf-8")
    csv_path = data._cache_path("batting", 2025, "csv")
    csv_path.write_text("a\n3\n", encoding="utf-8")

    expected = pd.DataFrame([{"a": 3}])

    def raise_parquet_error(_: Path) -> pd.DataFrame:
        raise ImportError("missing optional dependency 'pyarrow'")

    monkeypatch.setattr(pd, "read_parquet", raise_parquet_error)
    monkeypatch.setattr(pd, "read_csv", lambda _: expected)

    got = data._read_cache("batting", 2025)
    pd.testing.assert_frame_equal(got, expected)


def test_read_cache_parquet_read_error_without_csv_returns_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(data, "CACHE_ROOT", tmp_path)
    parquet_path = data._cache_path("pitching", 2025, "parquet")
    parquet_path.write_text("placeholder", encoding="utf-8")

    def raise_parquet_error(_: Path) -> pd.DataFrame:
        raise ValueError("corrupt parquet")

    monkeypatch.setattr(pd, "read_parquet", raise_parquet_error)

    assert data._read_cache("pitching", 2025) is None

def test_read_cache_no_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(data, "CACHE_ROOT", tmp_path)
    assert data._read_cache("batting", 2030) is None


def test_atomic_write_frame_replaces_target_and_cleans_temp(tmp_path: Path) -> None:
    target_path = tmp_path / "cache.parquet"
    target_path.write_text("old", encoding="utf-8")
    frame = pd.DataFrame([{"a": 1}])
    temp_paths: list[Path] = []

    def writer(_: pd.DataFrame, path: Path) -> None:
        temp_paths.append(path)
        path.write_text("new", encoding="utf-8")

    data._atomic_write_frame(frame, target_path, writer)

    assert target_path.read_text(encoding="utf-8") == "new"
    assert len(temp_paths) == 1
    assert not temp_paths[0].exists()


def test_atomic_write_frame_cleans_temp_when_writer_raises(tmp_path: Path) -> None:
    target_path = tmp_path / "cache.csv"
    frame = pd.DataFrame([{"a": 1}])
    temp_paths: list[Path] = []

    def failing_writer(_: pd.DataFrame, path: Path) -> None:
        temp_paths.append(path)
        path.write_text("partial", encoding="utf-8")
        raise RuntimeError("write failed")

    with pytest.raises(RuntimeError, match="write failed"):
        data._atomic_write_frame(frame, target_path, failing_writer)

    assert len(temp_paths) == 1
    assert not temp_paths[0].exists()
    assert not target_path.exists()


def test_write_cache_parquet_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(data, "CACHE_ROOT", tmp_path)
    calls: list[Path] = []

    def fake_atomic_write(
        frame: pd.DataFrame, target_path: Path, writer: Callable[[pd.DataFrame, Path], None]
    ) -> None:
        calls.append(target_path)

    monkeypatch.setattr(data, "_atomic_write_frame", fake_atomic_write)

    data._write_cache("batting", 2025, pd.DataFrame([{"a": 1}]))
    assert calls == [data._cache_path("batting", 2025, "parquet")]


def test_write_cache_csv_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(data, "CACHE_ROOT", tmp_path)
    calls: list[Path] = []

    def fake_atomic_write(
        frame: pd.DataFrame, target_path: Path, writer: Callable[[pd.DataFrame, Path], None]
    ) -> None:
        calls.append(target_path)
        if target_path.suffix == ".parquet":
            raise RuntimeError("boom")

    monkeypatch.setattr(data, "_atomic_write_frame", fake_atomic_write)

    data._write_cache("pitching", 2025, pd.DataFrame([{"a": 1}]))

    assert calls == [
        data._cache_path("pitching", 2025, "parquet"),
        data._cache_path("pitching", 2025, "csv"),
    ]
    assert "Parquet cache write failed" in caplog.text


@pytest.mark.parametrize(
    ("kind", "stats_attr", "expected"),
    [
        ("batting", "batting_stats", pd.DataFrame([{"a": 1}])),
        ("pitching", "pitching_stats", pd.DataFrame([{"a": 2}])),
    ],
)
def test_fetch_season_stats_fetch_success(
    disable_cache_io: None,
    install_fake_pybaseball: Callable[..., types.SimpleNamespace],
    kind: str,
    stats_attr: str,
    expected: pd.DataFrame,
) -> None:
    install_fake_pybaseball(
        batting_stats=(
            lambda year: expected if stats_attr == "batting_stats" else pd.DataFrame([{"a": 9}])
        ),
        pitching_stats=(
            lambda year: expected if stats_attr == "pitching_stats" else pd.DataFrame([{"a": 9}])
        ),
    )

    got = data.fetch_season_stats(2025, kind, use_cache=False)
    pd.testing.assert_frame_equal(got, expected)


def test_fetch_season_stats_cache_hit(monkeypatch: pytest.MonkeyPatch) -> None:
    cached = pd.DataFrame([{"a": 1}])
    monkeypatch.setattr(data, "_read_cache", lambda kind, year: cached)
    got = data.fetch_season_stats(2025, "batting", use_cache=True)
    pd.testing.assert_frame_equal(got, cached)


@pytest.mark.parametrize("kind", ["fielding", ["batting"], {"kind": "pitching"}])
def test_fetch_season_stats_invalid_kind(kind: object) -> None:
    with pytest.raises(DataFetchError, match=r"^Invalid kind"):
        data.fetch_season_stats(2025, kind, use_cache=False)  # type: ignore[arg-type]


def test_fetch_season_stats_pybaseball_exception(
    monkeypatch: pytest.MonkeyPatch, install_fake_pybaseball: Callable[..., types.SimpleNamespace]
) -> None:
    monkeypatch.setattr(data, "_read_cache", lambda kind, year: None)
    install_fake_pybaseball(
        batting_stats=lambda year: (_ for _ in ()).throw(RuntimeError("down")),
        pitching_stats=lambda year: pd.DataFrame([{"a": 9}]),
    )

    with pytest.raises(DataFetchError, match=r"^Unable to fetch batting stats"):
        data.fetch_season_stats(2025, "batting", use_cache=False)


def test_fetch_season_stats_empty_dataframe(
    monkeypatch: pytest.MonkeyPatch, install_fake_pybaseball: Callable[..., types.SimpleNamespace]
) -> None:
    monkeypatch.setattr(data, "_read_cache", lambda kind, year: None)
    install_fake_pybaseball(
        batting_stats=lambda year: pd.DataFrame(),
        pitching_stats=lambda year: pd.DataFrame([{"a": 9}]),
    )

    with pytest.raises(DataFetchError, match=r"^No batting stats returned"):
        data.fetch_season_stats(2025, "batting", use_cache=False)


def test_lookup_player_ids_first_last_validation() -> None:
    with pytest.raises(PlayerLookupError, match=r"^Provide both first and last name\."):
        data.lookup_player_ids("Madonna")


def test_lookup_player_ids_success(
    install_fake_pybaseball: Callable[..., types.SimpleNamespace],
) -> None:
    expected = pd.DataFrame([{"key_fangraphs": 123}])
    install_fake_pybaseball(playerid_lookup=lambda last, first: expected)

    got = data.lookup_player_ids("Mike Trout")
    pd.testing.assert_frame_equal(got, expected)


def test_lookup_player_ids_pybaseball_exception(
    install_fake_pybaseball: Callable[..., types.SimpleNamespace],
) -> None:
    install_fake_pybaseball(
        playerid_lookup=lambda last, first: (_ for _ in ()).throw(RuntimeError("network"))
    )

    with pytest.raises(PlayerLookupError, match=r"^Failed player lookup"):
        data.lookup_player_ids("Mike Trout")


def test_lookup_player_ids_empty_result(
    install_fake_pybaseball: Callable[..., types.SimpleNamespace],
) -> None:
    install_fake_pybaseball(playerid_lookup=lambda last, first: pd.DataFrame())

    with pytest.raises(PlayerLookupError, match=r"^No player found"):
        data.lookup_player_ids("Mike Trout")
