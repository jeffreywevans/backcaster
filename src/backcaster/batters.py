"""Population-level batter projections; no projected-year statistics are read."""

from __future__ import annotations

import numpy as np
import pandas as pd

from backcaster.marcel import ProjectionError
from backcaster.normalize import safe_divide
from backcaster.stat_columns import BATTING_STAT_COLUMNS, CONTEXT_STATS, IDENTITY_COLUMNS

EVENTS = ["1B", "2B", "3B", "HR", "BB", "HBP", "SO", "SH", "SF", "OUT"]


def _events(frame: pd.DataFrame) -> pd.DataFrame:
    events = frame.reindex(columns=EVENTS, fill_value=0).astype(float)
    events["1B"] = frame["H"] - frame["2B"] - frame["3B"] - frame["HR"]
    events["OUT"] = frame["AB"] - frame["H"] - frame["SO"]
    if not np.isfinite(events.to_numpy()).all() or (events < 0).any().any():
        raise ProjectionError(
            "Batter counts must be finite and consistent (H <= AB, SO <= AB - H)."
        )
    return events


def _rebaseline(events: pd.DataFrame, pa: pd.Series, target: pd.Series) -> pd.DataFrame:
    """Rake mutually exclusive events to fixed player PA and league event totals."""
    desired = target * float(pa.sum())
    # Positive league outcomes must be reachable, including a historically absent
    # event in the projected population. Seed only those cells, then rake.
    values = events.clip(lower=1e-12).mul(desired.gt(0), axis=1)
    for _ in range(200):
        values = values.mul(desired.div(values.sum()).fillna(0), axis=1)
        values = values.mul(pa.div(values.sum(axis=1)).fillna(0), axis=0)
        if np.allclose(values.sum(), desired, rtol=1e-10, atol=1e-8):
            return values
    raise ProjectionError("Batter league rebaselining did not converge.")


def _context_counts(history: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    counts = history[list(CONTEXT_STATS)].astype(float)
    if not np.isfinite(counts.to_numpy()).all() or (counts < 0).any().any():
        raise ProjectionError("Contextual batter counts must be finite and nonnegative.")
    if (counts["IBB"] > history["BB"]).any() or (counts["GDP"] > events["OUT"]).any():
        raise ProjectionError(
            "IBB must not exceed BB and GDP must not exceed non-strikeout AB outs."
        )
    return counts


def _regress(
    history: pd.DataFrame, counts: pd.DataFrame, year: int
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    weights = history["Season"].map({year - 1: 5.0, year - 2: 4.0, year - 3: 3.0})
    exposure = history["PA"] * weights
    league_pa = history.groupby("Season")["PA"].sum()
    if year - 1 not in league_pa:
        raise ProjectionError("Latest completed season has no non-pitcher batting PA.")
    league_rates = counts.groupby(history["Season"]).sum().div(league_pa, axis=0)
    expected = league_rates.reindex(history["Season"]).set_axis(history.index).mul(exposure, axis=0)
    evidence = counts.mul(weights, axis=0).groupby(history["PlayerID"]).sum()
    evidence_pa = exposure.groupby(history["PlayerID"]).sum()
    baseline = expected.groupby(history["PlayerID"]).sum().div(evidence_pa, axis=0)
    return (evidence + 1200 * baseline).div(evidence_pa + 1200, axis=0), evidence_pa, league_rates


def _playing_time(history: pd.DataFrame, year: int) -> pd.Series:
    prior = (
        history.pivot_table(index="PlayerID", columns="Season", values="PA", aggfunc="sum")
        .reindex(columns=[year - 1, year - 2], fill_value=0)
        .fillna(0)
    )
    return 0.5 * prior[year - 1] + 0.1 * prior[year - 2] + 200


def _age_rates(
    rates: pd.DataFrame, people: pd.DataFrame, year: int
) -> tuple[pd.DataFrame, pd.Series]:
    birth = pd.to_numeric(people["birthYear"], errors="coerce")
    age = year - birth
    if birth.isna().any() or not np.isfinite(age).all() or ((age < 15) | (age > 70)).any():
        raise ProjectionError(
            "Valid birthYear is required for every batter in the projection population."
        )
    adjustment = (age - 29) * np.where(age > 29, 0.003, 0.006)
    aged = rates.copy()
    positive = ["1B", "2B", "3B", "HR", "BB", "HBP", "R", "RBI", "SB", "IBB"]
    negative = ["SO", "OUT", "CS", "GDP"]
    aged[positive] = aged[positive].mul(1 - adjustment, axis=0)
    aged[negative] = aged[negative].mul(1 + adjustment, axis=0)
    return aged, age


def _bounded_rebaseline(values: pd.Series, target: float, cap: pd.Series) -> pd.Series:
    """Preserve a contextual league total while respecting per-player capacity."""
    capacity = float(cap.sum())
    tolerance = max(1e-8, capacity * 1e-9)
    if target < 0 or target > capacity + tolerance:
        raise ProjectionError("Contextual league target exceeds its available event capacity.")
    if target == 0:
        return values * 0
    if target >= capacity:
        return cap.copy()
    # Normalize weights so target/smallest weight is a finite upper bound.
    weights = np.maximum(values.to_numpy(dtype=float), 1e-12)
    weights = weights / float(weights.max())
    limits = cap.to_numpy(dtype=float)
    low, high = 0.0, target / float(weights.min())
    for _ in range(150):
        scale = (low + high) / 2
        result = np.minimum(weights * scale, limits)
        if float(result.sum()) < target:
            low = scale
        else:
            high = scale
    return pd.Series(
        np.minimum(weights * ((low + high) / 2), limits), index=values.index, name=values.name
    )


def _project_context(
    rates: pd.DataFrame, pa: pd.Series, target: pd.Series, events: pd.DataFrame
) -> pd.DataFrame:
    projected = rates[list(CONTEXT_STATS)].mul(pa, axis=0)
    desired = target[list(CONTEXT_STATS)] * float(pa.sum())
    # Runs/RBI/baserunning are overlapping events, not extra PA outcomes.
    for stat in ["R", "RBI", "SB", "CS"]:
        projected[stat] *= safe_divide(float(desired[stat]), float(projected[stat].sum()))
    projected["IBB"] = _bounded_rebaseline(projected["IBB"], float(desired["IBB"]), events["BB"])
    projected["GDP"] = _bounded_rebaseline(projected["GDP"], float(desired["GDP"]), events["OUT"])
    return projected


def _summarize(projected: pd.DataFrame, pa: pd.Series) -> pd.DataFrame:
    out = projected.copy()
    out["H"] = out[["1B", "2B", "3B", "HR"]].sum(axis=1)
    out["AB"] = out["H"] + out["SO"] + out["OUT"]
    out["PA"] = pa
    out["TB"] = out["H"] + out["2B"] + 2 * out["3B"] + 3 * out["HR"]
    out["BA"] = out["H"] / out["AB"].replace(0, np.nan)
    # BB includes IBB already. SB/CS/R/RBI/GDP do not add PA or total bases.
    out["OBP"] = (out["H"] + out["BB"] + out["HBP"]) / (
        out["AB"] + out["BB"] + out["HBP"] + out["SF"]
    ).replace(0, np.nan)
    out["SLG"] = out["TB"] / out["AB"].replace(0, np.nan)
    out["OPS"] = out["OBP"] + out["SLG"]
    return out


def project_batters(seasons: pd.DataFrame, year: int) -> pd.DataFrame:
    """Use all non-pitcher seasons for regression and population rebaselining."""
    history = seasons[seasons["Season"].isin([year - 1, year - 2, year - 3])].copy()
    if history.empty:
        raise ProjectionError("No non-pitcher batting history in the three prior seasons.")
    history = history[history["PA"] > 0].copy()
    events = _events(history)
    counts = events.join(_context_counts(history, events))
    rates, evidence_pa, league_rates = _regress(history, counts, year)
    pa = _playing_time(history, year)
    people = (
        history.sort_values("Season")
        .drop_duplicates("PlayerID", keep="last")
        .set_index("PlayerID")
        .reindex(rates.index)
    )
    rates, age = _age_rates(rates, people, year)
    event_rates = rates[EVENTS].div(rates[EVENTS].sum(axis=1), axis=0)
    target = league_rates.loc[[year - 1]].iloc[0]
    projected = _rebaseline(event_rates.mul(pa, axis=0), pa, target[EVENTS])
    context = _project_context(rates, pa, target, projected)
    out = _summarize(projected.join(context), pa)
    out["Reliability"] = evidence_pa / (evidence_pa + 1200)
    out["ConfidenceTier"] = np.where(out["Reliability"] >= 0.5, "core", "low-sample")
    out["Age"], out["Name"], out["Year"] = age, people["Name"], year
    out = out.reset_index()
    return out[[*IDENTITY_COLUMNS, *BATTING_STAT_COLUMNS, "Reliability", "ConfidenceTier"]]
