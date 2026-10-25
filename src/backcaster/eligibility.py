"""Explicit, dated target-season eligibility decisions supplied by the caller."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from backcaster.data import DataLoadError


def read_eligibility(path: str | Path, year: int, as_of: str) -> pd.DataFrame:
    """Read one snapshot; unlisted players are excluded, regardless of sample size."""
    try:
        if date.fromisoformat(as_of).isoformat() != as_of:
            raise ValueError("noncanonical date")
    except ValueError as exc:
        raise ValueError("--as-of must be an ISO date: YYYY-MM-DD") from exc
    required = {"PlayerID", "Year", "AsOf", "Eligible"}
    try:
        frame = pd.read_csv(
            path,
            encoding="utf-8-sig",
            dtype=str,
            usecols=lambda column: column in required | {"Team"},
        )
    except (OSError, ValueError) as exc:
        raise DataLoadError(f"Unable to read eligibility snapshot '{path}': {exc}") from exc
    missing = required - set(frame)
    if missing:
        raise DataLoadError(f"Eligibility snapshot missing columns: {', '.join(sorted(missing))}.")
    snapshot = frame[(frame.Year == str(year)) & (frame.AsOf == as_of)].copy()
    if snapshot.empty:
        raise DataLoadError(f"Eligibility snapshot has no rows for Year={year}, AsOf={as_of}.")
    if snapshot.PlayerID.isna().any() or snapshot.PlayerID.str.strip().eq("").any():
        raise DataLoadError(
            "Eligibility snapshot requires a nonempty Lahman PlayerID for every row."
        )
    snapshot["PlayerID"] = snapshot.PlayerID.str.strip()
    if snapshot.PlayerID.duplicated().any():
        raise DataLoadError("Duplicate PlayerID in the selected eligibility snapshot.")
    decisions = snapshot.Eligible.str.strip().str.casefold()
    if not decisions.isin(["true", "false"]).all():
        raise DataLoadError("Eligibility snapshot Eligible values must be true or false.")
    snapshot["Eligible"] = decisions.eq("true")
    return snapshot.set_index("PlayerID")
