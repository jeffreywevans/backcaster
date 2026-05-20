from __future__ import annotations

import runpy
from argparse import Namespace
from typing import Any

import pandas as pd
import pytest

from backcaster import cli
from backcaster.cli import (
    _prior_years,
    _render,
    build_parser,
    main,
    run_batch,
    run_player,
    run_team,
)
from backcaster.data import DataFetchError, PlayerLookupError
from backcaster.marcel import ProjectionError


def _team_args(**overrides: object) -> Namespace:
    args = {
        "team": "NYY",
        "year": 2026,
        "kind": "batting",
        "format": "cli",
        "out": None,
    }
    args.update(overrides)
    return Namespace(**args)


def _player_args(**overrides: object) -> Namespace:
    args = {
        "name": "John Smith",
        "year": 2026,
        "kind": "batting",
        "format": "cli",
        "out": None,
    }
    args.update(overrides)
    return Namespace(**args)


def _stub_render(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backcaster.cli._render", lambda *_a, **_k: None)


def _stub_player_lookup(monkeypatch: pytest.MonkeyPatch, fangraphs_id: Any = 101) -> None:
    monkeypatch.setattr(
        "backcaster.cli.lookup_player_ids", lambda _n: pd.DataFrame([{"name_given": "John Smith"}])
    )
    monkeypatch.setattr(
        "backcaster.cli.resolve_player_lookup", lambda *_a: {"key_fangraphs": fangraphs_id}
    )


def test_prior_years_returns_previous_three() -> None:
    assert _prior_years(2026) == (2025, 2024, 2023)


def test_render_cli_prints_table(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    df = pd.DataFrame([{"Name": "A"}])
    monkeypatch.setattr("backcaster.cli.to_cli_table", lambda _df: "CLI TABLE")
    _render(df, "cli", None)
    assert capsys.readouterr().out.strip() == "CLI TABLE"


@pytest.mark.parametrize("fmt", ["csv", "html"])
def test_render_file_writers(monkeypatch: pytest.MonkeyPatch, tmp_path, fmt: str) -> None:
    df = pd.DataFrame([{"Name": "A"}])
    out = tmp_path / f"out.{fmt}"
    called: dict[str, object] = {}

    def _fake_writer(input_df: pd.DataFrame, path: str) -> None:
        called["df"] = input_df
        called["path"] = path

    monkeypatch.setitem(cli._FILE_RENDERERS, fmt, _fake_writer)
    _render(df, fmt, str(out))

    assert called["path"] == str(out)
    pd.testing.assert_frame_equal(called["df"], df)


@pytest.mark.parametrize("fmt", ["csv", "html"])
def test_render_file_formats_require_out(fmt: str) -> None:
    with pytest.raises(ValueError, match="--out is required"):
        _render(pd.DataFrame([{"Name": "A"}]), fmt, None)


def test_render_rejects_unsupported_format() -> None:
    with pytest.raises(ValueError, match="Unsupported format: pdf"):
        _render(pd.DataFrame([{"Name": "A"}]), "pdf", None)


def test_run_team_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "backcaster.cli.fetch_season_stats",
        lambda y, _k: pd.DataFrame([{"Team": "NYY", "WAR": y}]),
    )
    monkeypatch.setattr(
        "backcaster.cli.project_team", lambda *_a, **_k: pd.DataFrame([{"Team": "NYY"}])
    )
    _stub_render(monkeypatch)

    assert run_team(_team_args()) == 0


def test_run_team_raises_when_missing_season(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "backcaster.cli.fetch_season_stats", lambda _y, _k: pd.DataFrame([{"Team": "BOS"}])
    )

    with pytest.raises(ProjectionError, match="Missing season 2025 for team 'NYY'"):
        run_team(_team_args())


def test_run_team_missing_team_column_raises_data_fetch_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "backcaster.cli.fetch_season_stats", lambda _y, _k: pd.DataFrame([{"WAR": 5.1}])
    )

    with pytest.raises(
        DataFetchError, match=r"Season 2025 batting stats missing required column\(s\): Team\."
    ):
        run_team(_team_args())


def test_run_batch_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "backcaster.cli.fetch_season_stats", lambda y, _k: pd.DataFrame([{"Name": f"P{y}"}])
    )
    monkeypatch.setattr(
        "backcaster.cli.project_team", lambda *_a, **_k: pd.DataFrame([{"Name": "Projected"}])
    )
    _stub_render(monkeypatch)

    assert run_batch(Namespace(year=2026, kind="batting", format="cli", out=None)) == 0


def test_main_success_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backcaster.cli.run_team", lambda _args: 0)
    parser = build_parser()
    parsed = parser.parse_args(["team", "--year", "2026", "--kind", "batting", "--team", "NYY"])
    assert parsed.func(parsed) == 0


@pytest.mark.parametrize(
    ("exc", "msg"),
    [
        (DataFetchError("fetch failed"), "fetch failed"),
        (PlayerLookupError("lookup failed"), "lookup failed"),
        (ProjectionError("projection failed"), "projection failed"),
        (ValueError("bad value"), "bad value"),
    ],
)
def test_main_error_handling(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    exc: Exception,
    msg: str,
) -> None:
    def _boom(_args: Namespace) -> int:
        raise exc

    monkeypatch.setattr("backcaster.cli.run_team", _boom)

    rc = main(["team", "--year", "2026", "--kind", "batting", "--team", "NYY"])

    assert rc == 2
    assert f"Error: {msg}" in capsys.readouterr().err


def test_main_block_via_runpy_warns_and_exits() -> None:
    with pytest.warns(RuntimeWarning, match="backcaster.cli"):
        with pytest.raises(SystemExit, match="2"):
            runpy.run_module("backcaster.cli", run_name="__main__")


def test_run_player_matches_fangraphs_id_successfully(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_player_lookup(monkeypatch, fangraphs_id=101)
    monkeypatch.setattr(
        "backcaster.cli.fetch_season_stats",
        lambda y, _k: pd.DataFrame([{"IDfg": 101, "Name": "Someone Else", "PA": 500, "Season": y}]),
    )
    monkeypatch.setattr(
        "backcaster.cli.project_player", lambda *_a, **_k: pd.DataFrame([{"Name": "John Smith"}])
    )
    _stub_render(monkeypatch)

    assert run_player(_player_args()) == 0


def test_run_player_missing_idfg_column_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_player_lookup(monkeypatch, fangraphs_id=101)
    monkeypatch.setattr(
        "backcaster.cli.fetch_season_stats", lambda _y, _k: pd.DataFrame([{"Name": "John Smith"}])
    )

    with pytest.raises(ProjectionError, match="Missing season 2025"):
        run_player(_player_args())


def test_run_player_blank_fangraphs_id_falls_back_to_name(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_player_lookup(monkeypatch, fangraphs_id=float("nan"))
    monkeypatch.setattr(
        "backcaster.cli.fetch_season_stats",
        lambda _y, _k: pd.DataFrame([{"Name": "john smith", "PA": 500}]),
    )
    monkeypatch.setattr(
        "backcaster.cli.project_player", lambda *_a, **_k: pd.DataFrame([{"Name": "John Smith"}])
    )
    _stub_render(monkeypatch)

    assert run_player(_player_args()) == 0


def test_run_player_name_fallback_failure_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_player_lookup(monkeypatch, fangraphs_id=None)
    monkeypatch.setattr(
        "backcaster.cli.fetch_season_stats", lambda _y, _k: pd.DataFrame([{"Name": "Not Him"}])
    )

    with pytest.raises(ProjectionError, match="Missing season 2025"):
        run_player(_player_args())


def test_run_player_duplicate_id_rows_are_handled(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_player_lookup(monkeypatch, fangraphs_id=101)
    monkeypatch.setattr(
        "backcaster.cli.fetch_season_stats",
        lambda _y, _k: pd.DataFrame(
            [
                {"IDfg": 101, "Name": "John Smith", "PA": 500},
                {"IDfg": 101, "Name": "John Smith", "PA": 510},
            ]
        ),
    )
    monkeypatch.setattr(
        "backcaster.cli.project_player", lambda *_a, **_k: pd.DataFrame([{"Name": "John Smith"}])
    )
    _stub_render(monkeypatch)

    assert run_player(_player_args()) == 0
