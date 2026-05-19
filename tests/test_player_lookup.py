import pandas as pd
import pytest

from backcaster.data import (
    PlayerLookupError,
    _filter_candidates_by_name,
    resolve_player_lookup,
)


def test_resolve_player_lookup_picks_single_exact_candidate_in_window() -> None:
    lookup = pd.DataFrame(
        [
            {
                "name_first": "Juan",
                "name_last": "Soto",
                "name_given": "Juan Jose Soto",
                "key_fangraphs": 20123,
                "mlb_played_first": 2018,
                "mlb_played_last": 2026,
            },
            {
                "name_first": "Juan",
                "name_last": "Soto",
                "name_given": "Juan Soto",
                "key_fangraphs": 99999,
                "mlb_played_first": 1988,
                "mlb_played_last": 1992,
            },
        ]
    )

    resolved = resolve_player_lookup("Juan Soto", lookup, [2025, 2024, 2023])
    assert int(resolved["key_fangraphs"]) == 20123


def test_resolve_player_lookup_raises_clear_duplicate_error() -> None:
    lookup = pd.DataFrame(
        [
            {
                "name_first": "John",
                "name_last": "Smith",
                "name_given": "John Smith",
                "key_fangraphs": 101,
                "mlb_played_first": 2001,
                "mlb_played_last": 2004,
            },
            {
                "name_first": "John",
                "name_last": "Smith",
                "name_given": "John Smith",
                "key_fangraphs": 102,
                "mlb_played_first": 2001,
                "mlb_played_last": 2004,
            },
        ]
    )

    with pytest.raises(PlayerLookupError, match="Duplicate player match"):
        resolve_player_lookup("John Smith", lookup, [2003, 2002, 2001])


def test_filter_candidates_by_name_gracefully_handles_missing_name_columns() -> None:
    lookup = pd.DataFrame(
        [
            {"name_first": "John", "key_fangraphs": 1},
            {"name_first": "Jane", "key_fangraphs": 2},
        ]
    )

    filtered = _filter_candidates_by_name("john smith", lookup)

    pd.testing.assert_frame_equal(filtered, lookup)


def test_filter_candidates_by_name_handles_categorical_name_columns() -> None:
    lookup = pd.DataFrame(
        {
            "name_first": pd.Series(["Bob", None], dtype="category"),
            "name_last": pd.Series(["Smith", "Jones"], dtype="category"),
            "name_given": pd.Series(["Bob Smith", None], dtype="category"),
            "key_fangraphs": [7, 9],
        }
    )

    filtered = _filter_candidates_by_name("bob smith", lookup)

    assert len(filtered) == 1
    assert int(filtered.iloc[0]["key_fangraphs"]) == 7
