from __future__ import annotations

import runpy

import pandas as pd
import pytest

from backcaster import cli
from backcaster.cli import _default_data_dir, _render, _validate_output_options, build_parser, main
from backcaster.data import DataLoadError, PlayerLookupError
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
@pytest.mark.parametrize("out", [None, ""])
def test_render_file_formats_require_out(fmt: str, out: str | None) -> None:
    df = pd.DataFrame([{"Name": "A"}])
    with pytest.raises(ValueError, match="--out is required"):
        _render(df, fmt, out)


def test_render_rejects_unsupported_format() -> None:
    df = pd.DataFrame([{"Name": "A"}])
    with pytest.raises(ValueError, match="Unsupported format: pdf"):
        _render(df, "pdf", None)


@pytest.mark.parametrize(
    ("exc", "msg"),
    [
        (DataLoadError("data load failed"), "data load failed"),
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


@pytest.mark.parametrize("selectors", [[], ["--name", "Chris Young", "--player-id", "youngch01"]])
def test_player_requires_one_selector(selectors: list[str]) -> None:
    parser = build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["player", "--year", "2022", "--kind", "batting", *selectors])
    assert exc.value.code == 2


@pytest.mark.parametrize("fmt", ["csv", "html"])
def test_unwritable_output_reports_cli_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path, capsys: pytest.CaptureFixture[str], fmt: str
) -> None:
    monkeypatch.setattr(
        "backcaster.cli.LahmanSource.project", lambda *args, **kwargs: pd.DataFrame([{"Name": "A"}])
    )
    # A directory as the destination fails even when tests run with elevated privileges.
    assert main(["hitters", "--year", "2026", "--format", fmt, "--out", str(tmp_path)]) == 2
    captured = capsys.readouterr()
    assert "Error:" in captured.err
    assert str(tmp_path) in captured.err
    assert "Traceback" not in captured.err
    assert captured.out == ""


@pytest.mark.parametrize(
    "options, message",
    [
        (["--out", "ignored.csv"], "--out cannot be used with --format cli"),
        (["--format", "cli", "--out", "ignored.csv"], "--out cannot be used with --format cli"),
        (["--format", "csv"], "--out is required"),
        (["--format", "html"], "--out is required"),
    ],
)
def test_invalid_output_options_fail_before_loading_data(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    options: list[str],
    message: str,
) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("invalid output options attempted data loading")

    monkeypatch.setattr("backcaster.cli.LahmanSource.project", forbidden)
    assert main(["hitters", "--year", "2026", *options]) == 2
    captured = capsys.readouterr()
    assert message in captured.err
    assert captured.out == ""


def test_validation_rejects_cli_output_path(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(ValueError, match="--out cannot be used"):
        _validate_output_options("cli", "ignored.csv")
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "options, message",
    [
        (["--as-of", "2025-01-14"], "must be provided together"),
        (["--eligibility-file", "eligibility.csv"], "must be provided together"),
        (
            [
                "--eligibility-file",
                "eligibility.csv",
                "--as-of",
                "2025-01-14",
                "--kind",
                "pitching",
            ],
            "batting projections only",
        ),
    ],
)
def test_cli_eligibility_options_validate_before_data_loading(
    tmp_path, capsys: pytest.CaptureFixture[str], options: list[str], message: str
) -> None:
    assert (
        main(
            ["batch", "--year", "2025", "--kind", "batting", "--data-dir", str(tmp_path), *options]
        )
        == 2
    )
    assert message in capsys.readouterr().err
