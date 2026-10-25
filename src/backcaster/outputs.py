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


def _format_variance(value: Any, column: str) -> str:
    """Format actual-minus-projected differences with an explicit direction."""
    if pd.isna(value):
        return ""
    if column == "IP":
        outs = int((Decimal(str(value)) * 3).to_integral_value(rounding=ROUND_HALF_UP))
        sign = "+" if outs > 0 else "-" if outs < 0 else ""
        whole, remainder = divmod(abs(outs), 3)
        return f"{sign}{whole}.{remainder}"
    places = RATE_PLACES.get(column, 0)
    number = Decimal(str(value)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    sign = "+" if number > 0 else ""
    return f"{sign}{number:.{places}f}"


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


def _display_variances(projected: pd.DataFrame, actuals: pd.DataFrame) -> pd.DataFrame:
    if "PlayerID" not in projected or "PlayerID" not in actuals:
        raise ValueError("Historical comparison requires PlayerID in projections and actuals.")
    stats = PITCHING_STAT_COLUMNS if "IP" in projected else BATTING_STAT_COLUMNS
    actual_by_id = actuals.set_index("PlayerID")
    rows: list[dict[str, Any]] = []
    for projection in projected.to_dict(orient="records"):
        player_id = projection["PlayerID"]
        row: dict[str, Any] = {"PlayerID": player_id}
        if player_id in actual_by_id.index:
            actual = actual_by_id.loc[player_id]
            for column in stats:
                if column in projection and column in actual:
                    row[column] = _format_variance(actual[column] - projection[column], column)
        rows.append(row)
    return pd.DataFrame(rows)


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


def to_html(df: pd.DataFrame, out_path: str | Path, actuals: pd.DataFrame | None = None) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    actual_display = _display_frame(actuals) if actuals is not None else None
    variances = _display_variances(df, actuals) if actuals is not None else None
    html = render_report(_display_frame(df), actual_display, variances)
    out.write_text(html, encoding="utf-8")
    return out
