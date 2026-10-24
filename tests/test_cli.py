from __future__ import annotations

import runpy

import pandas as pd
import pytest

from backcaster import cli
from backcaster.cli import _default_data_dir, _render, build_parser, main
from backcaster.data import DataFetchError, PlayerLookupError
from backcaster.marcel import ProjectionError


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
    df = pd.DataFrame([{"Name": "A"}])
    with pytest.raises(ValueError, match="--out is required"):
        _render(df, fmt, None)


def test_render_rejects_unsupported_format() -> None:
    df = pd.DataFrame([{"Name": "A"}])
    with pytest.raises(ValueError, match="Unsupported format: pdf"):
        _render(df, "pdf", None)


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
    def _boom(*_args, **_kwargs):
        raise exc

    monkeypatch.setattr("backcaster.cli.LahmanSource.project", _boom)

    rc = main(["team", "--year", "2026", "--kind", "batting", "--team", "NYY"])

    assert rc == 2
    assert f"Error: {msg}" in capsys.readouterr().err


def test_main_block_via_runpy_warns_and_exits() -> None:
    expected_exit = pytest.raises(SystemExit, match="2")
    expected_warning = pytest.warns(RuntimeWarning, match="backcaster.cli")
    with expected_exit, expected_warning:
        runpy.run_module("backcaster.cli", run_name="__main__")


@pytest.mark.parametrize("platform, expected", [("win32", "C:/Baseball/lahman"), ("linux", None)])
def test_default_data_directory(
    monkeypatch: pytest.MonkeyPatch, platform: str, expected: str | None
) -> None:
    from pathlib import Path

    monkeypatch.delenv("LAHMAN_DATA_DIR", raising=False)
    monkeypatch.setattr(cli.sys, "platform", platform)
    assert _default_data_dir() == (expected or str(Path.home() / "Baseball" / "lahman"))


def test_data_directory_precedence(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("LAHMAN_DATA_DIR", str(tmp_path))
    parser = build_parser()
    args = ["batch", "--year", "2024", "--kind", "batting"]
    assert parser.parse_args(args).data_dir == str(tmp_path)
    assert parser.parse_args([*args, "--data-dir", "custom"]).data_dir == "custom"
