from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import pandas as pd

from backcaster.html_report import render_report
from backcaster.stat_columns import BATTING_STAT_COLUMNS, IDENTITY_COLUMNS, PITCHING_STAT_COLUMNS

COUNT_COLUMNS = {
    "TB",
    "PA",
    "AB",
    "H",
    "2B",
    "3B",
    "HR",
    "BB",
    "SO",
    "HBP",
    "SF",
    "SH",
    "ER",
    "BF",
    "R",
    "RBI",
    "SB",
    "CS",
    "IBB",
    "GDP",
    "GIDP",
    "W",
    "L",
    "SV",
    "G",
    "GS",
    "CG",
    "SHO",
    "WP",
    "BK",
    "Age",
    "Year",
}
RATE_PLACES = {
    "Reliability": 6,
    "BA": 3,
    "AVG": 3,
    "OBP": 3,
    "SLG": 3,
    "OPS": 3,
    "ERA": 2,
    "WHIP": 3,
    "W-L%": 3,
    "H9": 1,
    "HR9": 1,
    "BB9": 1,
    "SO9": 1,
    "SO/W": 2,
}


def _format_number(value: Any, places: int) -> str:
    if pd.isna(value):
        return ""
    number = Decimal(str(value)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    return f"{number:.{places}f}"


def _format_innings(value: Any) -> str:
    if pd.isna(value):
        return ""
    innings = Decimal(str(value))
    if not innings.is_finite() or innings < 0:
        raise ValueError("IP must be a finite, nonnegative number of decimal innings.")
    outs = int((innings * 3).to_integral_value(rounding=ROUND_HALF_UP))
    whole, remainder = divmod(outs, 3)
    return f"{whole}.{remainder}"


def _display_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Format a copy at the output boundary; preserve full-precision calculations."""
    display = df.copy()
    for column in display.columns:
        if column == "IP":
            display[column] = display[column].map(_format_innings)
        elif column in COUNT_COLUMNS or column in RATE_PLACES:
            places = RATE_PLACES.get(column, 0)
            display[column] = display[column].map(
                lambda value, places=places: _format_number(value, places)
            )
    stats = PITCHING_STAT_COLUMNS if "IP" in display else BATTING_STAT_COLUMNS
    ordered = [c for c in (*IDENTITY_COLUMNS, *stats, "Reliability") if c in display]
    ordered += [c for c in display if c not in ordered]
    return display.loc[:, ordered]


def to_cli_table(df: pd.DataFrame) -> str:
    return _display_frame(df).to_string(index=False)


def to_csv(df: pd.DataFrame, out_path: str | Path) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    display = _display_frame(df)
    for column in ("Name", "PlayerID"):
        if column in display:
            # CSV quoting alone does not prevent spreadsheet formula execution.
            display[column] = display[column].map(
                lambda value: (
                    "'" + value
                    if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r"))
                    else value
                )
            )
    display.to_csv(out, index=False)
    return out


def to_html(df: pd.DataFrame, out_path: str | Path) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    html = render_report(_display_frame(df))
    out.write_text(html, encoding="utf-8")
    return out
