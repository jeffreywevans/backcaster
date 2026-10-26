"""Exercise real Tk controls and worker delivery; run under xvfb-run on Linux."""

import gc
import os
import time
import tkinter as tk
from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import pytest

import test_lahman
from backcaster import __version__, gui


@pytest.fixture
def lahman_data(tmp_path):
    return test_lahman.lahman.__wrapped__(tmp_path)


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    try:
        window = tk.Tk()
    except tk.TclError:
        if os.environ.get("DISPLAY"):
            raise
        pytest.skip("Tk requires a display; use xvfb-run to run GUI integration tests")
    # Keep destroyed Tcl interpreters from being collected on a worker thread.
    gc.collect()
    gc.disable()
    window.withdraw()
    monkeypatch.setattr(gui, "settings_path", lambda: tmp_path / "settings.json")
    monkeypatch.setattr(gui.messagebox, "showerror", Mock())
    app = gui.Workspace(window)
    yield app
    window.destroy()
    gc.collect()
    gc.enable()


def settle(app):
    deadline = time.monotonic() + 10
    while str(app.controls[0]["state"]) == "disabled":
        app.window.update()
        if time.monotonic() > deadline:
            pytest.fail("GUI worker did not deliver its result")
        time.sleep(0.005)


def test_window_identity_and_default_controls(workspace):
    app = workspace
    assert app.window.title() == f"Backcaster · v{__version__}"
    assert app.scope.get() == "All hitters"
    assert str(app.kind_box["state"]) == "disabled"
    assert str(app.csv_button["state"]) == "disabled"
    assert str(app.html_button["state"]) == "disabled"
    app._poll()  # An empty queue should keep polling without showing an error.
    gui.messagebox.showerror.assert_not_called()


@pytest.mark.parametrize(
    "scope,kind,player_state,team_state",
    [
        ("Particular player", "batting", "normal", "disabled"),
        ("Team", "batting", "disabled", "normal"),
        ("All pitchers", "pitching", "disabled", "disabled"),
        ("All hitters", "batting", "disabled", "disabled"),
    ],
)
def test_scope_controls(workspace, scope, kind, player_state, team_state):
    app = workspace
    app.scope.set(scope)
    app.scope_box.event_generate("<<ComboboxSelected>>")
    app.window.update()
    assert app.kind.get() == kind
    assert str(app.player_box["state"]) == player_state
    assert str(app.team_box["state"]) == team_state


def test_load_local_selections_and_save_folders(workspace, lahman_data, monkeypatch, tmp_path):
    app = workspace
    monkeypatch.setattr(gui.filedialog, "askdirectory", lambda **kwargs: str(lahman_data))
    app._browse(app.data_dir)
    assert gui.load_settings(app.path)["data_dir"] == str(lahman_data)
    app._load()
    settle(app)
    assert app.year.get() == "2022"
    assert "Test Star [star]" in app.player_box["values"]
    assert "BOS" in app.team_box["values"]
    app.output_dir.set(str(tmp_path / "reports"))
    app._save()
    assert gui.load_settings(app.path)["output_dir"] == str(tmp_path / "reports")
    monkeypatch.setattr(gui.filedialog, "askdirectory", lambda **kwargs: "")
    app._browse(app.data_dir)
    assert app.data_dir.get() == str(lahman_data)
    app.data_dir.set(str(tmp_path / "missing"))
    app._load()
    settle(app)
    assert "Operation failed" in app.status.get()
    gui.messagebox.showerror.assert_called_once()


@pytest.mark.parametrize(
    "scope,selector",
    [
        ("All hitters", ""),
        ("All pitchers", ""),
        ("Team", "BOS"),
        ("Particular player", "Test Star [star]"),
        ("Particular player", "Test Star"),
        ("Particular player", "star"),
    ],
)
def test_generate_with_real_lahman_engine(workspace, lahman_data, scope, selector):
    app = workspace
    app.data_dir.set(str(lahman_data))
    app.year.set("2022")
    app.scope.set(scope)
    app._scope_changed()
    app.player.set(selector)
    app.team.set(selector)
    app._generate()
    settle(app)
    gui.messagebox.showerror.assert_not_called()
    assert app.result is not None
    assert not app.result.empty
    assert len(app.tree.get_children()) == len(app.result)
    for column in ("Year", "Age", "Reliability"):
        assert str(app.tree.column(column, "anchor")) == "center"
    for column in ("Name", "PlayerID", "ConfidenceTier"):
        assert str(app.tree.column(column, "anchor")) == "w"
    numeric_stat = "IP" if scope == "All pitchers" else "PA"
    assert str(app.tree.column(numeric_stat, "anchor")) == "center"
    assert "2022" in app.summary.get()
    assert str(app.csv_button["state"]) == "normal"
    if scope == "Particular player":
        assert app.result.PlayerID.tolist() == ["star"]
    if scope == "All pitchers":
        assert "IP" in app.result
    else:
        assert "AB" in app.result


@pytest.mark.parametrize(
    "year,scope",
    [
        ("bad", "All hitters"),
        ("1873", "All hitters"),
        ("10000", "All hitters"),
        ("2022", "Particular player"),
        ("2022", "Team"),
    ],
)
def test_invalid_filters_do_not_start_projection(workspace, year, scope):
    app = workspace
    app.year.set(year)
    app.scope.set(scope)
    app._generate()
    gui.messagebox.showerror.assert_called_once()
    assert app.result is None
    assert str(app.controls[0]["state"]) == "normal"


def test_preview_limit_empty_results_and_worker_errors(workspace, monkeypatch):
    app = workspace
    frame = pd.DataFrame({"Name": ["Player"] * 501, "PlayerID": ["p"] * 501, "Year": [2022] * 501})
    source = Mock()
    source.project.return_value = frame
    monkeypatch.setattr(gui, "LahmanSource", lambda directory: source)
    app._generate()
    settle(app)
    assert len(app.tree.get_children()) == 500
    assert len(app.result) == 501
    source.project.side_effect = ValueError("Invalid data")
    app._generate()
    settle(app)
    assert "Invalid data" in app.status.get()
    assert app.result is frame  # A failed request retains the last successful report.
    assert str(app.html_button["state"]) == "normal"
    source.project.side_effect = None
    source.project.return_value = frame.head(0)
    app._generate()
    settle(app)
    assert len(app.tree.get_children()) == 0
    assert str(app.html_button["state"]) == "disabled"


@pytest.mark.parametrize("format", ["csv", "html"])
def test_export_complete_report_through_save_dialog(workspace, tmp_path, monkeypatch, format):
    app = workspace
    app.result = pd.DataFrame(
        {"Name": ["Player"] * 501, "PlayerID": ["p"] * 501, "Year": [2022] * 501}
    )
    root = tmp_path / "reports"
    app.output_dir.set(str(root))
    destination = root / f"report.{format}"
    dialog = Mock(return_value=str(destination))
    monkeypatch.setattr(gui.filedialog, "asksaveasfilename", dialog)
    app._export(format)
    settle(app)
    assert destination.is_file()
    assert "Exported 501 players" in app.status.get()
    assert dialog.call_args.kwargs["initialdir"] == str(root)
    if format == "csv":
        assert len(pd.read_csv(destination)) == 501
    else:
        assert destination.read_text().count("Player") >= 501


def test_export_guards_cancellation_and_path_errors(workspace, tmp_path, monkeypatch):
    app = workspace
    dialog = Mock(return_value="")
    monkeypatch.setattr(gui.filedialog, "asksaveasfilename", dialog)
    app._export("csv")
    app.result = pd.DataFrame()
    app._export("csv")
    dialog.assert_not_called()
    app.result = pd.DataFrame([{"Name": "Player", "PlayerID": "p", "Year": 2022}])
    app.output_dir.set("")
    app._export("csv")
    gui.messagebox.showerror.assert_called_once()
    app.output_dir.set(str(tmp_path / "reports"))
    app._export("csv")
    assert not list((tmp_path / "reports").iterdir())
    blocked = tmp_path / "file"
    blocked.write_text("not a directory")
    app.output_dir.set(str(blocked))
    app._export("csv")
    assert "Cannot create output folder" in gui.messagebox.showerror.call_args.args[1]
    app.output_dir.set(str(tmp_path / "reports"))
    dialog.return_value = str(tmp_path / "outside.csv")
    app._export("csv")
    settle(app)
    assert not (tmp_path / "outside.csv").exists()
    assert "selected output folder" in app.status.get()


def test_save_error_is_visible(workspace, monkeypatch):
    def fail(*args):
        raise OSError("read only")

    monkeypatch.setattr(gui, "save_settings", fail)
    workspace._save()
    assert "read only" in gui.messagebox.showerror.call_args.args[1]


@pytest.mark.parametrize(
    "platform,variable", [("win32", "APPDATA"), ("linux", "XDG_CONFIG_HOME"), ("darwin", None)]
)
def test_settings_location(monkeypatch, tmp_path, platform, variable):
    monkeypatch.setattr(gui.sys, "platform", platform)
    if variable:
        monkeypatch.setenv(variable, str(tmp_path))
        assert gui.settings_path() == tmp_path / "backcaster" / "settings.json"
    else:
        assert (
            gui.settings_path()
            == Path.home() / "Library/Application Support/backcaster/settings.json"
        )


def test_atomic_save_preserves_previous_preferences_on_failure(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    gui.save_settings(path, {"data_dir": "original"})

    def fail(*args):
        raise OSError("replace failed")

    monkeypatch.setattr(gui.os, "replace", fail)
    with pytest.raises(OSError, match="replace failed"):
        gui.save_settings(path, {"data_dir": "new"})
    assert gui.load_settings(path) == {"data_dir": "original"}
    assert list(tmp_path.iterdir()) == [path]


def test_main_starts_workspace_and_event_loop(monkeypatch):
    window = Mock()
    workspace = Mock()
    monkeypatch.setattr(gui.tk, "Tk", lambda: window)
    monkeypatch.setattr(gui, "Workspace", workspace)
    gui.main()
    workspace.assert_called_once_with(window)
    window.mainloop.assert_called_once()


def test_main_explains_missing_display(monkeypatch):
    def fail():
        raise tk.TclError("no display")

    monkeypatch.setattr(gui.tk, "Tk", fail)
    with pytest.raises(SystemExit, match="requires a graphical desktop"):
        gui.main()


def test_loading_without_complete_history_preserves_selected_season(workspace, monkeypatch):
    app = workspace
    app.year.set("2022")
    monkeypatch.setattr(gui, "load_choices", lambda directory: ([], [], []))
    app._load()
    settle(app)
    assert app.year.get() == "2022"
    assert not app.season_box["values"]
    assert not app.player_box["values"]
    assert not app.team_box["values"]
    assert "Loaded 0 players and 0 team IDs" in app.status.get()
    gui.messagebox.showerror.assert_not_called()


def test_module_entrypoint_explains_missing_display(monkeypatch):
    import runpy

    def fail():
        raise tk.TclError("no display")

    monkeypatch.setattr(tk, "Tk", fail)
    with pytest.raises(SystemExit, match="requires a graphical desktop: no display"):
        runpy.run_path(gui.__file__, run_name="__main__")


@pytest.mark.parametrize("scope", ["All hitters", "All pitchers"])
@pytest.mark.parametrize("format", ["html", "csv"])
def test_comparison_toggle_preview_and_exports(
    workspace, lahman_data, tmp_path, monkeypatch, scope, format
):
    for table in ("Batting", "Pitching", "Teams", "Appearances"):
        path = lahman_data / f"{table}.csv"
        history = pd.read_csv(path)
        actual = history[history.yearID == 2021].copy()
        actual["yearID"] = 2022
        if "HR" in actual:
            actual["HR"] += 1
        pd.concat([history, actual], ignore_index=True).to_csv(path, index=False)
    app = workspace
    app.data_dir.set(str(lahman_data))
    app.year.set("2022")
    app.scope.set(scope)
    app._scope_changed()
    assert app.compare.get() == "No"
    app.compare.set("Yes")
    app._generate()
    settle(app)
    gui.messagebox.showerror.assert_not_called()
    assert app.actuals is not None
    assert "Actual HR" in app.tree["columns"]
    assert "Variance HR" in app.tree["columns"]
    assert str(app.tree.column("Actual HR", "anchor")) == "center"
    assert str(app.tree.column("Variance HR", "anchor")) == "center"
    assert "Actuals & variance" in app.summary.get()
    # Exports must use the generated comparison even if the toggle changes later.
    app.compare.set("No")
    app.output_dir.set(str(tmp_path / "reports"))
    destination = tmp_path / "reports" / f"comparison.{format}"
    monkeypatch.setattr(gui.filedialog, "asksaveasfilename", lambda **kwargs: str(destination))
    app._export(format)
    settle(app)
    if format == "csv":
        exported = pd.read_csv(destination)
        assert len(exported) == len(app.result)
        for row in exported.itertuples(index=False):
            assert row.ActualStatus == "Available"
        row = exported.iloc[0]
        actual = app.actuals.set_index("PlayerID").loc[row.PlayerID]
        projection = app.result.set_index("PlayerID").loc[row.PlayerID]
        assert row["Actual HR"] == actual.HR
        assert row["Variance HR"] == round(actual.HR - projection.HR)
    else:
        text = destination.read_text()
        assert 'class="detail-row actual-row"' in text
        assert 'class="detail-row variance-row"' in text
    app._generate()
    settle(app)
    assert app.actuals is None
    assert "Actual HR" not in app.tree["columns"]


def test_comparison_without_actuals_preserves_last_report(workspace, lahman_data, monkeypatch):
    app = workspace
    app.data_dir.set(str(lahman_data))
    app.year.set("2022")
    app._generate()
    settle(app)
    previous = app.result
    monkeypatch.setattr(gui.LahmanSource, "actuals", lambda *args: pd.DataFrame())
    app.compare.set("Yes")
    app._generate()
    settle(app)
    assert "No actual results available" in app.status.get()
    assert app.result is previous
    assert app.actuals is None
