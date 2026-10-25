"""Offline projections from extracted Lahman CSV files."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from backcaster.batters import project_batters
from backcaster.data import DataLoadError, PlayerLookupError
from backcaster.marcel import ProjectionError, project_player, project_team


class LahmanSource:
    def __init__(self, directory: str) -> None:
        self.directory = Path(directory)
        self.tables: dict[str, pd.DataFrame] = {}
        self._requested_columns: dict[str, set[str]] = {}
        self._people: pd.DataFrame | None = None

    def read(self, name: str, required: set[str]) -> pd.DataFrame:
        optional = {"Batting": {"HBP", "SF", "SH"}, "People": {"birthYear"}}.get(name, set())
        columns = required | optional
        if name not in self.tables or columns - self._requested_columns[name]:
            columns |= self._requested_columns.get(name, set())
            paths = [
                p for p in self.directory.glob("*") if p.name.casefold() == f"{name}.csv".casefold()
            ]
            if len(paths) != 1:
                raise DataLoadError(
                    f"Expected {name}.csv in Lahman directory '{self.directory}'. "
                    "Extract the Lahman CSVs there or select their directory with --data-dir."
                )
            try:
                self.tables[name] = pd.read_csv(
                    paths[0],
                    encoding="utf-8-sig",
                    low_memory=False,
                    usecols=lambda column: column in columns,
                )
                self._requested_columns[name] = columns
            except (OSError, ValueError) as exc:
                raise DataLoadError(f"Unable to read Lahman {name}.csv: {exc}") from exc
        frame = self.tables[name]
        missing = required - set(frame.columns)
        if missing:
            raise DataLoadError(f"Lahman {name}.csv missing columns: {', '.join(sorted(missing))}.")
        return frame

    def season(self, year: int, kind: str, *, qualified: bool = True) -> pd.DataFrame:
        if kind not in {"batting", "pitching"}:
            raise DataLoadError(f"Invalid kind {kind!r}.")
        name = "Batting" if kind == "batting" else "Pitching"
        components = (
            ["AB", "H", "2B", "3B", "HR", "BB", "SO", "R", "RBI", "SB", "CS", "IBB", "GIDP"]
            if kind == "batting"
            else [
                "IPouts",
                "ER",
                "H",
                "HR",
                "BB",
                "SO",
                "BFP",
                "W",
                "L",
                "SV",
                "R",
                "IBB",
                "HBP",
                "BK",
                "WP",
            ]
        )
        stats = self.read(name, {"playerID", "yearID", "stint", "teamID", *components})
        stats = stats[stats["yearID"] == year].copy()
        if stats.empty:
            raise DataLoadError(
                f"Lahman {name}.csv has no data for {year}; choose a covered year or update the dataset."
            )
        games = self._season_games(year)
        if kind == "batting":
            for column in ["HBP", "SF", "SH"]:
                if column not in stats:
                    stats[column] = 0
            components += ["HBP", "SF", "SH"]
        try:
            stats[components] = stats[components].apply(pd.to_numeric, errors="raise").fillna(0)
            stats["stint"] = pd.to_numeric(stats["stint"], errors="raise")
        except (ValueError, TypeError) as exc:
            raise DataLoadError(
                f"Invalid numeric data in Lahman {name}.csv for {year}: {exc}"
            ) from exc
        totals = stats.groupby("playerID", sort=False)[components].sum()
        latest = (
            stats.sort_values("stint", kind="stable")
            .drop_duplicates("playerID", keep="last")
            .set_index("playerID")
        )
        totals["Team"] = latest["teamID"]
        if kind == "batting":
            totals["PA"] = totals[["AB", "BB", "HBP", "SF", "SH"]].sum(axis=1)
            minimum_pa = int(3.1 * games + 0.5)
            totals["Qualified"] = totals["PA"] >= minimum_pa
        else:
            totals["IP"] = totals["IPouts"] / 3
            totals["BF"] = totals["BFP"]
            totals["Qualified"] = totals["IPouts"] >= 3 * games
        if qualified:
            totals = totals[totals["Qualified"]]
        if totals.empty:
            raise DataLoadError(f"No qualified {kind} players in Lahman for {year}.")
        totals = totals.rename(columns={"GIDP": "GDP"})
        totals = self._attach_names(totals)
        totals["PlayerID"] = totals["playerID"]
        totals["Season"] = year
        return totals

    def _season_games(self, year: int) -> float:
        teams = self.read("Teams", {"yearID", "teamID", "G"})
        games = pd.to_numeric(teams.loc[teams["yearID"] == year, "G"], errors="coerce").max()
        if pd.isna(games) or games <= 0:
            raise DataLoadError(f"Lahman Teams.csv has no valid game counts for {year}.")
        return float(games)

    def _attach_names(self, totals: pd.DataFrame) -> pd.DataFrame:
        if self._people is None:
            people = self.read("People", {"playerID", "nameFirst", "nameLast"})
            if people["playerID"].duplicated().any():
                raise DataLoadError("Duplicate player IDs in Lahman People.csv.")
            names = (
                people["nameFirst"].fillna("") + " " + people["nameLast"].fillna("")
            ).str.strip()
            self._people = people.assign(Name=names).set_index("playerID")
            self._people = self._people[["Name", *(["birthYear"] if "birthYear" in people else [])]]
        totals = totals.reset_index()
        for column in self._people:
            totals[column] = totals["playerID"].map(self._people[column])
        if totals["Name"].isna().any():
            raise DataLoadError(
                "Lahman People.csv is missing players present in season statistics."
            )
        return totals

    def project(
        self,
        command: str,
        year: int,
        kind: str,
        name: str | None = None,
        team: str | None = None,
        player_id: str | None = None,
    ) -> pd.DataFrame:
        if name is not None and player_id is not None:
            raise ValueError("Specify either name or player_id, not both.")
        batting = pd.DataFrame()
        if kind == "batting":
            seasons, batting = self._batting_population(year)
        else:
            self.read("People", {"playerID", "nameFirst", "nameLast", "birthYear"})
            seasons = pd.concat(
                [self.season(y, kind, qualified=False) for y in (year - 1, year - 2, year - 3)],
                ignore_index=True,
            )
        eligible = seasons[seasons["Qualified"]]
        if command == "player":
            candidates = self._player_seasons(eligible, name, player_id)
            matches = seasons[seasons["PlayerID"] == candidates["PlayerID"].iloc[0]]
            if kind == "batting":
                return batting[batting["PlayerID"] == matches["PlayerID"].iloc[0]].reset_index(
                    drop=True
                )
            return project_player(
                str(matches["Name"].iloc[0]), matches, kind, year, league_df=eligible
            ).assign(PlayerID=matches["PlayerID"].iloc[0])
        selected = eligible
        if command == "team":
            selected = eligible[eligible["Team"].str.casefold() == (team or "").casefold()]
            if selected.empty:
                raise ProjectionError(
                    f"No qualified players for Lahman team ID '{team}' in the prior three seasons."
                )
        if kind == "batting":
            return batting[batting["PlayerID"].isin(selected["PlayerID"])].reset_index(drop=True)
        history = seasons[seasons["PlayerID"].isin(selected["PlayerID"])]
        return project_team(history, kind, year, baseline_df=eligible)

    def _batting_population(self, year: int) -> tuple[pd.DataFrame, pd.DataFrame]:
        self.read("People", {"playerID", "nameFirst", "nameLast", "birthYear"})
        seasons = pd.concat(
            [self.season(y, "batting", qualified=False) for y in (year - 1, year - 2, year - 3)],
            ignore_index=True,
        )
        appearances = self.read("Appearances", {"playerID", "yearID", "G_all", "G_p"})
        appearances = appearances[appearances["yearID"].isin([year - 1, year - 2, year - 3])].copy()
        try:
            appearances[["G_all", "G_p"]] = appearances[["G_all", "G_p"]].apply(
                pd.to_numeric, errors="raise"
            )
        except (ValueError, TypeError) as exc:
            raise DataLoadError("Invalid game counts in Lahman Appearances.csv.") from exc
        counts = appearances[["G_all", "G_p"]]
        invalid = counts.replace([float("inf"), -float("inf")], float("nan")).isna() | (counts < 0)
        if invalid.any().any() or (appearances["G_p"] > appearances["G_all"]).any():
            raise DataLoadError("Invalid game counts in Lahman Appearances.csv.")
        games = appearances.groupby(["playerID", "yearID"])[["G_all", "G_p"]].sum(min_count=1)
        seasons = seasons.merge(games, left_on=["PlayerID", "Season"], right_index=True, how="left")
        if seasons[["G_all", "G_p"]].isna().any().any():
            raise DataLoadError(
                "Appearances.csv must cover every batting player-season with game counts."
            )
        # A primary pitcher appears as pitcher in more than half of their games.
        # Retain two-way hitters whose batting appearances outnumber pitching games.
        seasons = seasons[seasons["G_p"] <= seasons["G_all"] / 2].copy()
        ages = year - pd.to_numeric(seasons["birthYear"], errors="coerce")
        valid_age = ages.between(15, 70)
        excluded = seasons.loc[~valid_age, "PlayerID"].drop_duplicates().tolist()
        if excluded:
            preview = ", ".join(excluded[:10]) + (", ..." if len(excluded) > 10 else "")
            logging.getLogger(__name__).warning(
                "Skipping %d non-pitcher batters with missing or invalid birthYear "
                "(projection age must be 15–70). Player IDs: %s",
                len(excluded),
                preview,
            )
            seasons = seasons.loc[valid_age].copy()
            if seasons.empty:
                raise ProjectionError(
                    "No non-pitcher batters with valid birthYear remain in the prior three seasons."
                )
        projected = project_batters(seasons, year)
        qualified = seasons[seasons["Qualified"]]
        if qualified.empty:
            raise ProjectionError("No qualified non-pitcher batters in the prior three seasons.")
        return seasons, projected

    def _player_seasons(
        self, seasons: pd.DataFrame, name: str | None, player_id: str | None = None
    ) -> pd.DataFrame:
        if player_id is not None:
            matches = seasons[seasons["PlayerID"] == player_id]
            if matches.empty:
                raise PlayerLookupError(
                    f"No qualified Lahman player found for player ID '{player_id}' "
                    "in the prior three seasons."
                )
            return matches
        normalized = " ".join((name or "").casefold().split())
        matches = seasons[
            seasons["Name"].map(lambda value: " ".join(value.casefold().split())) == normalized
        ]
        ids = matches["PlayerID"].unique()
        if len(ids) == 0:
            raise PlayerLookupError(
                f"No qualified Lahman player found for '{name}' in the prior three seasons."
            )
        if len(ids) > 1:
            raise PlayerLookupError(
                f"Ambiguous Lahman name '{name}'; matching player IDs: {', '.join(ids)}. "
                "Select one with --player-id instead of --name."
            )
        return matches
