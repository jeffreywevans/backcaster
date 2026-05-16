from __future__ import annotations

import argparse
import sys

import pandas as pd

from marcelball.data import (
    DataFetchError,
    PlayerLookupError,
    fetch_season_stats,
    lookup_player_ids,
    resolve_player_lookup,
)
from marcelball.marcel import ProjectionError, project_player, project_team
from marcelball.outputs import to_cli_table, to_csv, to_html

_FILE_RENDERERS = {"csv": to_csv, "html": to_html}
_OUTPUT_FORMAT_CHOICES = ("cli", *_FILE_RENDERERS.keys())


def _prior_years(year: int) -> tuple[int, int, int]:
    return year - 1, year - 2, year - 3


def _render(df: pd.DataFrame, output_format: str, out: str | None) -> None:
    if output_format == "cli":
        print(to_cli_table(df))
    elif output_format in _FILE_RENDERERS:
        if not out:
            raise ValueError(f"--out is required for {output_format} output")
        _FILE_RENDERERS[output_format](df, out)
    else:
        raise ValueError(f"Unsupported format: {output_format}")


def run_player(args: argparse.Namespace) -> int:
    years = _prior_years(args.year)
    pid_df = lookup_player_ids(args.name)
    resolved = resolve_player_lookup(args.name, pid_df, years)
    fg_key = resolved.get("key_fangraphs")
    fg_key_str = str(int(fg_key)) if pd.notna(fg_key) else None

    frames = []
    league_frames = []
    for y in years:
        df = fetch_season_stats(y, args.kind)
        league = df.copy()
        league["Season"] = y
        league_frames.append(league)

        row = pd.DataFrame()
        if fg_key_str and "IDfg" in league.columns:
            fg_numeric = pd.to_numeric(fg_key_str, errors="coerce")
            idfg_numeric = pd.to_numeric(league["IDfg"], errors="coerce")
            if pd.notna(fg_numeric):
                row = league[idfg_numeric == fg_numeric].copy()

        if row.empty:
            row = league[league["Name"].astype(str).str.casefold() == args.name.casefold()].copy()
        if row.empty:
            raise ProjectionError(f"Missing season {y} for player '{args.name}'.")
        frames.append(row)

    prior = pd.concat(frames, ignore_index=True).sort_values("Season", ascending=False)
    league_prior = pd.concat(league_frames, ignore_index=True)
    proj = project_player(args.name, prior, args.kind, args.year, league_df=league_prior)
    _render(proj, args.format, args.out)
    return 0


def run_team(args: argparse.Namespace) -> int:
    years = _prior_years(args.year)
    frames = []
    for y in years:
        df = fetch_season_stats(y, args.kind)
        row = df[df["Team"] == args.team].copy()
        if row.empty:
            raise ProjectionError(f"Missing season {y} for team '{args.team}'.")
        row["Season"] = y
        frames.append(row)
    all_team = pd.concat(frames, ignore_index=True)
    proj = project_team(all_team, args.kind, args.year)
    _render(proj, args.format, args.out)
    return 0


def run_batch(args: argparse.Namespace) -> int:
    years = _prior_years(args.year)
    frames = []
    for y in years:
        df = fetch_season_stats(y, args.kind)
        df = df.copy()
        df["Season"] = y
        frames.append(df)
    all_players = pd.concat(frames, ignore_index=True)
    proj = project_team(all_players, args.kind, args.year)
    _render(proj, args.format, args.out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="marcelball")
    sub = p.add_subparsers(dest="command", required=True)

    def add_common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--year", type=int, required=True)
        sp.add_argument("--kind", choices=["batting", "pitching"], required=True)
        sp.add_argument("--format", choices=_OUTPUT_FORMAT_CHOICES, default="cli")
        sp.add_argument("--out")

    pp = sub.add_parser("player")
    add_common(pp)
    pp.add_argument("--name", required=True)
    pp.set_defaults(func=run_player)

    tp = sub.add_parser("team")
    add_common(tp)
    tp.add_argument("--team", required=True)
    tp.set_defaults(func=run_team)

    bp = sub.add_parser("batch")
    add_common(bp)
    bp.set_defaults(func=run_batch)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (DataFetchError, PlayerLookupError, ProjectionError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
