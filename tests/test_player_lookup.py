import pandas as pd
import pytest

from marcelball.data import PlayerLookupError, resolve_player_lookup


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
