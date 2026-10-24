from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

from backcaster.data import DataFetchError, PlayerLookupError
from backcaster.lahman import LahmanSource
from backcaster.marcel import ProjectionError
from backcaster.outputs import to_cli_table, to_csv, to_html

_FILE_RENDERERS = {"csv": to_csv, "html": to_html}
_OUTPUT_FORMAT_CHOICES = ("cli", *_FILE_RENDERERS.keys())


def _default_data_dir() -> str:
    default = (
        "C:/Baseball/lahman"
        if sys.platform == "win32"
        else str(Path.home() / "Baseball" / "lahman")
    )
    return os.environ.get("LAHMAN_DATA_DIR", default)


def _render(df: pd.DataFrame, output_format: str, out: str | None) -> None:
    if output_format == "cli":
        print(to_cli_table(df))
    elif output_format in _FILE_RENDERERS:
        if not out:
            raise ValueError(f"--out is required for {output_format} output")
        _FILE_RENDERERS[output_format](df, out)
    else:
        raise ValueError(f"Unsupported format: {output_format}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="backcaster")
    sub = p.add_subparsers(dest="command", required=True)

    def add_common(sp: argparse.ArgumentParser, kind: str | None = None) -> None:
        sp.add_argument("--year", type=int, required=True)
        if kind is None:
            sp.add_argument("--kind", choices=["batting", "pitching"], required=True)
        else:
            sp.set_defaults(kind=kind)
        sp.add_argument("--format", choices=_OUTPUT_FORMAT_CHOICES, default="cli")
        sp.add_argument("--out")
        sp.add_argument(
            "--data-dir",
            default=_default_data_dir(),
            help="Lahman CSV directory (default: LAHMAN_DATA_DIR, C:/Baseball/lahman on Windows, or ~/Baseball/lahman)",
        )

    pp = sub.add_parser("player")
    add_common(pp)
    pp.add_argument("--name", required=True)

    tp = sub.add_parser("team")
    add_common(tp)
    tp.add_argument("--team", required=True)

    bp = sub.add_parser("batch")
    add_common(bp)
    for command, kind in [("hitters", "batting"), ("pitchers", "pitching")]:
        league = sub.add_parser(command, help=f"Project all eligible {command} across all teams")
        add_common(league, kind)
        league.set_defaults(command="batch")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = LahmanSource(args.data_dir).project(
            args.command,
            args.year,
            args.kind,
            name=getattr(args, "name", None),
            team=getattr(args, "team", None),
        )
        _render(result, args.format, args.out)
        return 0
    except (DataFetchError, PlayerLookupError, ProjectionError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
