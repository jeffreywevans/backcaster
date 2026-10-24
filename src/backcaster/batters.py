"""Population-level batter projections; no projected-year statistics are read."""

from __future__ import annotations

import numpy as np
import pandas as pd

from backcaster.marcel import BATTING_COMPONENTS, ProjectionError

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


def project_batters(seasons: pd.DataFrame, year: int) -> pd.DataFrame:
    """Use all non-pitcher seasons for both regression and rebaselining."""
    history = seasons[seasons["Season"].isin([year - 1, year - 2, year - 3])].copy()
    if history.empty:
        raise ProjectionError("No non-pitcher batting history in the three prior seasons.")
    history = history[history["PA"] > 0].copy()
    counts = _events(history)
    weights = history["Season"].map({year - 1: 5.0, year - 2: 4.0, year - 3: 3.0})
    history["EvidencePA"] = history["PA"] * weights
    league_counts = counts.groupby(history["Season"]).sum()
    league_pa = history.groupby("Season")["PA"].sum()
    if year - 1 not in league_pa:
        raise ProjectionError("Latest completed season has no non-pitcher batting PA.")
    league_rates = league_counts.div(league_pa, axis=0)
    # Each player's exposure to each season determines their league average.
    expected = (
        league_rates.reindex(history["Season"])
        .set_axis(history.index)
        .mul(history["EvidencePA"], axis=0)
    )
    evidence = counts.mul(weights, axis=0).groupby(history["PlayerID"]).sum()
    evidence_pa = history.groupby("PlayerID")["EvidencePA"].sum()
    baseline = expected.groupby(history["PlayerID"]).sum().div(evidence_pa, axis=0)
    rates = (evidence + 1200 * baseline).div(evidence_pa + 1200, axis=0)
    prior_pa = (
        history.pivot_table(index="PlayerID", columns="Season", values="PA", aggfunc="sum")
        .reindex(columns=[year - 1, year - 2], fill_value=0)
        .fillna(0)
    )
    pa = 0.5 * prior_pa[year - 1] + 0.1 * prior_pa[year - 2] + 200
    people = (
        history.sort_values("Season")
        .drop_duplicates("PlayerID", keep="last")
        .set_index("PlayerID")
        .reindex(rates.index)
    )
    birth = pd.to_numeric(people["birthYear"], errors="coerce")
    age = year - birth
    if birth.isna().any() or not np.isfinite(age).all() or ((age < 15) | (age > 70)).any():
        raise ProjectionError(
            "Valid birthYear is required for every batter in the projection population."
        )
    adjustment = (age - 29) * np.where(age > 29, 0.003, 0.006)
    rates[["1B", "2B", "3B", "HR", "BB", "HBP"]] = rates[["1B", "2B", "3B", "HR", "BB", "HBP"]].mul(
        1 - adjustment, axis=0
    )
    rates[["SO", "OUT"]] = rates[["SO", "OUT"]].mul(1 + adjustment, axis=0)
    rates = rates.div(rates.sum(axis=1), axis=0)
    projected = _rebaseline(rates.mul(pa, axis=0), pa, league_rates.loc[[year - 1]].iloc[0])
    out = projected.copy()
    out["H"] = projected[["1B", "2B", "3B", "HR"]].sum(axis=1)
    out["AB"] = out["H"] + projected["SO"] + projected["OUT"]
    out["PA"] = pa
    out["AVG"] = out["H"] / out["AB"].replace(0, np.nan)
    out["OBP"] = (out["H"] + out["BB"] + out["HBP"]) / (
        out["AB"] + out["BB"] + out["HBP"] + out["SF"]
    ).replace(0, np.nan)
    out["SLG"] = (projected["1B"] + 2 * out["2B"] + 3 * out["3B"] + 4 * out["HR"]) / out[
        "AB"
    ].replace(0, np.nan)
    out["OPS"] = out["OBP"] + out["SLG"]
    out["Reliability"] = evidence_pa / (evidence_pa + 1200)
    out["Age"] = age
    out["Name"] = people["Name"]
    out["Year"] = year
    out = out.fillna(0).drop(columns=["1B", "OUT"]).reset_index()
    return out[
        [
            "PlayerID",
            *BATTING_COMPONENTS,
            "SH",
            "AVG",
            "OBP",
            "SLG",
            "OPS",
            "Reliability",
            "Age",
            "Name",
            "Year",
        ]
    ]
