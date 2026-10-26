"""Shared season ages, measured on June 30 of the requested year."""

from __future__ import annotations

import pandas as pd

BIRTH_COLUMNS = ("birthYear", "birthMonth", "birthDay")


def season_ages(people: pd.DataFrame, year: int) -> pd.Series:
    """Return June-30 ages; incomplete, fractional, or invalid dates yield NaN."""
    parts = people.reindex(columns=list(BIRTH_COLUMNS)).apply(pd.to_numeric, errors="coerce")
    dates = pd.to_datetime(
        parts.rename(columns=dict(zip(BIRTH_COLUMNS, ("year", "month", "day")))),
        errors="coerce",
    )
    ages = year - dates.dt.year - (dates.dt.month > 6).astype(int)
    return ages.where(parts.mod(1).eq(0).all(axis=1))
