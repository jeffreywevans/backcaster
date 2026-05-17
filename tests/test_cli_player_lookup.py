from argparse import Namespace

import pandas as pd
import pytest

from marcelball.cli import run_player
from marcelball.marcel import ProjectionError


def _args() -> Namespace:
    return Namespace(name="John Smith", year=2026, kind="batting", format="cli", out=None)


def test_run_player_does_not_fallback_to_name_after_fangraphs_id_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "marcelball.cli.lookup_player_ids",
        lambda _name: pd.DataFrame([{"name_given": "John Smith"}]),
    )
    monkeypatch.setattr(
        "marcelball.cli.resolve_player_lookup",
        lambda _name, _pid_df, _years: {"key_fangraphs": 101},
    )

    league_df = pd.DataFrame(
        [
            {"IDfg": 999, "Name": "John Smith", "PA": 500},
            {"IDfg": 888, "Name": "Other Player", "PA": 300},
        ]
    )
    monkeypatch.setattr("marcelball.cli.fetch_season_stats", lambda _year, _kind: league_df)

    with pytest.raises(ProjectionError, match="Missing season 2025"):
        run_player(_args())


def test_run_player_uses_name_fallback_when_no_fangraphs_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "marcelball.cli.lookup_player_ids",
        lambda _name: pd.DataFrame([{"name_given": "John Smith"}]),
    )
    monkeypatch.setattr(
        "marcelball.cli.resolve_player_lookup",
        lambda _name, _pid_df, _years: {"key_fangraphs": None},
    )

    league_df = pd.DataFrame([{"IDfg": 999, "Name": "John Smith", "PA": 500}])
    monkeypatch.setattr("marcelball.cli.fetch_season_stats", lambda _year, _kind: league_df)

    monkeypatch.setattr(
        "marcelball.cli.project_player",
        lambda *_args, **_kwargs: pd.DataFrame([{"Name": "John Smith"}]),
    )
    monkeypatch.setattr("marcelball.cli._render", lambda *_args, **_kwargs: None)

    assert run_player(_args()) == 0
