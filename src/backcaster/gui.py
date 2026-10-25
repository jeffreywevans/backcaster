"""Desktop report workspace. Run with ``backcaster-gui`` or ``python -m backcaster.gui``."""

from __future__ import annotations

import json
import os
import queue
import sys
import tempfile
import threading
import tkinter as tk
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

import pandas as pd

from backcaster import __version__
from backcaster.cli import _default_data_dir
from backcaster.lahman import LahmanSource
from backcaster.outputs import _display_frame, to_csv, to_html

APP_NAME = "Backcaster"
SCOPE_ALL_HITTERS = "All hitters"
UI_FONT = "Segoe UI"
ACCENT_BUTTON_STYLE = "Accent.TButton"
SCOPE_ALL_PITCHERS = "All pitchers"
SCOPE_PLAYER = "Particular player"


def settings_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return base / "backcaster" / "settings.json"


def load_settings(path: Path) -> dict[str, str]:
    try:
        values = json.loads(path.read_text(encoding="utf-8"))
        return (
            {k: v for k, v in values.items() if isinstance(v, str)}
            if isinstance(values, dict)
            else {}
        )
    except (OSError, ValueError):
        return {}


def save_settings(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as f:
            temporary = f.name
            json.dump(values, f, indent=2)
        os.replace(temporary, path)
    finally:
        if temporary and Path(temporary).exists():
            Path(temporary).unlink()


def load_choices(directory: str) -> tuple[list[str], list[str], list[str]]:
    source = LahmanSource(directory)
    people = source.read("People", {"playerID", "nameFirst", "nameLast"})
    names = (people.nameFirst.fillna("") + " " + people.nameLast.fillna("")).str.strip()
    players = sorted(f"{name} [{pid}]" for name, pid in zip(names, people.playerID, strict=True))
    years: set[int] = set()
    teams: set[str] = set()
    for table in ("Batting", "Pitching"):
        stats = source.read(table, {"yearID", "teamID"})
        years.update(int(y) for y in stats.yearID.dropna().unique())
        teams.update(str(t) for t in stats.teamID.dropna().unique())
    seasons = sorted((y + 1 for y in years if {y, y - 1, y - 2} <= years), reverse=True)
    return [str(y) for y in seasons], players, sorted(teams)


class Workspace:
    def __init__(self, window: tk.Tk) -> None:
        self.window = window
        self.path = settings_path()
        saved = load_settings(self.path)
        self.data_dir = tk.StringVar(value=saved.get("data_dir", _default_data_dir()))
        self.output_dir = tk.StringVar(value=saved.get("output_dir", str(Path.cwd() / "reports")))
        self.year = tk.StringVar(value=str(date.today().year))
        self.scope = tk.StringVar(value=SCOPE_ALL_HITTERS)
        self.kind = tk.StringVar(value="batting")
        self.player = tk.StringVar()
        self.team = tk.StringVar()
        self.status = tk.StringVar(
            value="Choose your Lahman data folder, then load selections to get started."
        )
        self.summary = tk.StringVar(value="No report generated")
        self.result: pd.DataFrame | None = None
        self.report_name = ""
        self.events: queue.Queue[tuple[bool, Any, Callable[[Any], None]]] = queue.Queue()
        self.controls: list[ttk.Button] = []
        self._build()
        self.window.after(100, self._poll)

    def _build(self) -> None:
        w = self.window
        w.title(f"{APP_NAME} · v{__version__}")
        w.geometry("1200x820")
        w.minsize(940, 720)
        w.configure(bg="#f3f6f5")
        style = ttk.Style(w)
        style.theme_use("clam")
        style.configure("TFrame", background="#f3f6f5")
        style.configure("TLabel", background="#f3f6f5", foreground="#203b3c", font=(UI_FONT, 10))
        style.configure("Title.TLabel", font=(UI_FONT, 23, "bold"))
        style.configure("Heading.TLabel", font=(UI_FONT, 12, "bold"))
        style.configure("TButton", padding=(14, 9), font=(UI_FONT, 10))
        style.configure(ACCENT_BUTTON_STYLE, background="#166b54", foreground="white")
        style.map(ACCENT_BUTTON_STYLE, background=[("active", "#0f5140")])
        style.configure(
            "Treeview",
            rowheight=29,
            background="white",
            fieldbackground="white",
            font=(UI_FONT, 10),
        )
        style.configure("Treeview.Heading", font=(UI_FONT, 10, "bold"), padding=8)
        rail = tk.Frame(w, bg="#143b3e", width=200)
        rail.pack(side="left", fill="y")
        rail.pack_propagate(False)
        for text, size, color in [
            ("◉  BACKCASTER", 15, "#a9e6bd"),
            ("BASEBALL ANALYTICS", 9, "#b6cbcc"),
            ("▤   Report workspace", 11, "white"),
        ]:
            tk.Label(
                rail, text=text, bg="#143b3e", fg=color, font=(UI_FONT, size), anchor="w"
            ).pack(fill="x", padx=18, pady=(25, 0))
        tk.Label(
            rail,
            text=f"{APP_NAME}\nv{__version__}\n\nLocal Lahman data\nMarcel projections",
            justify="left",
            bg="#143b3e",
            fg="#b6cbcc",
            font=(UI_FONT, 10),
            anchor="w",
        ).pack(side="bottom", fill="x", padx=18, pady=25)
        body = ttk.Frame(w, padding=24)
        body.pack(side="left", fill="both", expand=True)
        ttk.Label(body, text="Report workspace", style="Title.TLabel").pack(anchor="w")
        ttk.Label(body, text="Build a season outlook. Explore players. Export your report.").pack(
            anchor="w", pady=(5, 20)
        )
        setup = ttk.LabelFrame(body, text="  Data & report location  ", padding=12)
        setup.pack(fill="x")
        setup.columnconfigure(1, weight=1)
        self._folder_row(setup, 0, "Lahman CSV folder", self.data_dir)
        self._folder_row(setup, 1, "Report output folder", self.output_dir)
        self._button(setup, "Load selections", self._load).grid(
            row=2, column=1, sticky="w", pady=(8, 0)
        )
        self._button(setup, "Save folders", self._save).grid(
            row=2, column=2, padx=(10, 0), pady=(8, 0)
        )
        filters = ttk.LabelFrame(body, text="  Report filters  ", padding=12)
        filters.pack(fill="x", pady=16)
        for col in range(4):
            filters.columnconfigure(col, weight=1)
        self.season_box = self._combo(
            filters,
            0,
            0,
            "Projection season",
            self.year,
            [str(y) for y in range(date.today().year + 1, 1873, -1)],
        )
        self.scope_box = self._combo(
            filters,
            0,
            1,
            "Report scope",
            self.scope,
            [SCOPE_PLAYER, "Team", SCOPE_ALL_HITTERS, SCOPE_ALL_PITCHERS],
            True,
        )
        self.kind_box = self._combo(
            filters, 0, 2, "Statistics", self.kind, ["batting", "pitching"], True
        )
        self.player_box = self._combo(
            filters, 2, 0, "Player name or Lahman ID", self.player, [], span=2
        )
        self.team_box = self._combo(filters, 2, 2, "Lahman team ID", self.team, [], span=2)
        self.scope_box.bind("<<ComboboxSelected>>", lambda event: self._scope_changed())
        self._scope_changed()
        actions = ttk.Frame(body)
        actions.pack(fill="x", pady=(0, 16))
        self._button(actions, "Generate report", self._generate, ACCENT_BUTTON_STYLE).pack(
            side="left"
        )
        self.csv_button = self._button(actions, "Export CSV", lambda: self._export("csv"))
        self.csv_button.pack(side="right")
        self.html_button = self._button(actions, "Export HTML", lambda: self._export("html"))
        self.html_button.pack(side="right", padx=8)
        self._export_state(False)
        ttk.Label(body, textvariable=self.summary, style="Heading.TLabel").pack(
            anchor="w", pady=(0, 8)
        )
        table = ttk.Frame(body)
        table.pack(fill="both", expand=True)
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(table, show="headings")
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(table, orient="horizontal", command=self.tree.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        ttk.Label(body, textvariable=self.status, wraplength=760).pack(fill="x", pady=(14, 0))

    def _button(
        self, parent: Any, text: str, command: Callable[[], None], style: str = "TButton"
    ) -> ttk.Button:
        button = ttk.Button(parent, text=text, command=command, style=style)
        self.controls.append(button)
        return button

    def _folder_row(self, parent: Any, row: int, label: str, variable: tk.StringVar) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=4)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=4)
        self._button(parent, "Browse…", lambda: self._browse(variable)).grid(
            row=row, column=2, padx=(10, 0), pady=4
        )

    def _combo(
        self,
        parent: Any,
        row: int,
        col: int,
        label: str,
        variable: tk.StringVar,
        values: list[str],
        readonly: bool = False,
        span: int = 1,
    ) -> ttk.Combobox:
        ttk.Label(parent, text=label).grid(row=row, column=col, columnspan=span, sticky="w", padx=5)
        box = ttk.Combobox(
            parent,
            textvariable=variable,
            values=values,
            state="readonly" if readonly else "normal",
            width=22,
        )
        box.grid(row=row + 1, column=col, columnspan=span, sticky="ew", padx=5, pady=(5, 12))
        return box

    def _scope_changed(self) -> None:
        scope = self.scope.get()
        if scope in (SCOPE_ALL_HITTERS, SCOPE_ALL_PITCHERS):
            self.kind.set("batting" if scope == SCOPE_ALL_HITTERS else "pitching")
        self.kind_box.configure(state="disabled" if scope.startswith("All ") else "readonly")
        self.player_box.configure(state="normal" if scope == SCOPE_PLAYER else "disabled")
        self.team_box.configure(state="normal" if scope == "Team" else "disabled")

    def _browse(self, variable: tk.StringVar) -> None:
        folder = filedialog.askdirectory(
            parent=self.window, initialdir=variable.get(), mustexist=True
        )
        if folder:
            variable.set(folder)
            self._save()

    def _save(self) -> None:
        try:
            save_settings(
                self.path, {"data_dir": self.data_dir.get(), "output_dir": self.output_dir.get()}
            )
            self.status.set("Folder preferences saved.")
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"Could not save preferences: {exc}", parent=self.window)

    def _export_state(self, enabled: bool) -> None:
        for button in (self.csv_button, self.html_button):
            button.configure(state="normal" if enabled else "disabled")

    def _run(self, task: Callable[[], Any], done: Callable[[Any], None], status: str) -> None:
        for control in self.controls:
            control.configure(state="disabled")
        self.status.set(status)

        def work() -> None:
            try:
                self.events.put((True, task(), done))
            except Exception as exc:
                self.events.put((False, str(exc), done))

        threading.Thread(target=work, daemon=True).start()

    def _poll(self) -> None:
        try:
            success, result, done = self.events.get_nowait()
        except queue.Empty:
            pass
        else:
            for control in self.controls:
                control.configure(state="normal")
            self._export_state(self.result is not None and not self.result.empty)
            if success:
                done(result)
            else:
                self.status.set(f"Operation failed: {result}")
                messagebox.showerror(APP_NAME, result, parent=self.window)
        self.window.after(100, self._poll)

    def _load(self) -> None:
        directory = self.data_dir.get()

        def loaded(choices: tuple[list[str], list[str], list[str]]) -> None:
            seasons, players, teams = choices
            self.season_box.configure(values=seasons)
            self.player_box.configure(values=players)
            self.team_box.configure(values=teams)
            if seasons:
                self.year.set(seasons[0])
            self.status.set(
                f"Loaded {len(players):,} players and {len(teams)} team IDs. Select a season and report scope."
            )

        self._run(lambda: load_choices(directory), loaded, "Loading local Lahman selections…")

    def _projection_selection(self) -> tuple[str, int, str, str, dict[str, str]]:
        year = int(self.year.get())
        if not 1874 <= year <= 9999:
            raise ValueError("Choose a projection season between 1874 and 9999.")
        scope = self.scope.get()
        command = {
            SCOPE_PLAYER: "player",
            "Team": "team",
            SCOPE_ALL_HITTERS: "batch",
            SCOPE_ALL_PITCHERS: "batch",
        }[scope]
        kind = self.kind.get()
        kwargs: dict[str, str] = {}
        if command == "player":
            player = self.player.get().strip()
            if not player:
                raise ValueError("Select a player or enter a full name or Lahman player ID.")
            if player.endswith("]") and " [" in player:
                kwargs["player_id"] = player.rsplit(" [", 1)[1][:-1]
            else:
                kwargs["name" if " " in player else "player_id"] = player
        if command == "team":
            kwargs["team"] = self.team.get().strip()
            if not kwargs["team"]:
                raise ValueError("Select or enter a Lahman team ID.")
        return command, year, scope, kind, kwargs

    def _generate(self) -> None:
        try:
            command, year, scope, kind, kwargs = self._projection_selection()
        except ValueError as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self.window)
            return
        directory = self.data_dir.get()
        label = f"{year} · {scope} · {kind}"

        def generated(result: pd.DataFrame) -> None:
            self.result = result
            self.report_name = f"backcaster-{year}-{command}-{kind}"
            display = _display_frame(result)
            self.tree.delete(*self.tree.get_children())
            columns = list(display.columns)
            self.tree.configure(columns=columns)
            for column in columns:
                self.tree.heading(column, text=column)
                self.tree.column(column, width=160 if column == "Name" else 95, stretch=False)
            for values in display.head(500).itertuples(index=False, name=None):
                self.tree.insert("", "end", values=tuple(str(v) for v in values))
            self.summary.set(f"{label} — {len(result):,} players")
            self.status.set(
                "Report ready. Preview shows up to 500 players; exports include every result."
            )
            self._export_state(not result.empty)

        self._run(
            lambda: LahmanSource(directory).project(command, year, kind, **kwargs),
            generated,
            "Generating projections from the prior three seasons…",
        )

    def _export(self, format: str) -> None:
        if self.result is None or self.result.empty:
            return
        if not self.output_dir.get().strip():
            messagebox.showerror(
                APP_NAME, "Select a report output folder first.", parent=self.window
            )
            return
        root = Path(self.output_dir.get()).expanduser().resolve()
        try:
            root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror(
                APP_NAME, f"Cannot create output folder: {exc}", parent=self.window
            )
            return
        destination = filedialog.asksaveasfilename(
            parent=self.window,
            initialdir=str(root),
            initialfile=f"{self.report_name}-{datetime.now():%Y%m%d-%H%M%S}.{format}",
            defaultextension=f".{format}",
            filetypes=[(format.upper(), f"*.{format}")],
        )
        if not destination:
            return
        result = self.result.copy()
        renderer = to_csv if format == "csv" else to_html
        self._run(
            lambda: renderer(result, destination, output_root=root),
            lambda path: self.status.set(f"Exported {len(result):,} players to {path}"),
            f"Exporting {format.upper()} report…",
        )


def main() -> None:
    try:
        window = tk.Tk()
    except tk.TclError as exc:
        raise SystemExit(f"Backcaster GUI requires a graphical desktop: {exc}") from exc
    Workspace(window)
    window.mainloop()


if __name__ == "__main__":
    main()
