from __future__ import annotations

import pandas as pd

from marcelball.normalize import safe_divide
from marcelball.schemas import MarcelConfig


class ProjectionError(RuntimeError):
    pass


BATTING_COMPONENTS = ["PA", "AB", "H", "2B", "3B", "HR", "BB", "SO", "HBP", "SF"]
PITCHING_COMPONENTS = ["IP", "ER", "H", "HR", "BB", "SO", "BF"]


def _weighted_row(rows: list[pd.Series], weights: tuple[float, float, float], cols: list[str]) -> pd.Series:
    total_w = sum(weights[: len(rows)])
    out = {}
    for col in cols:
        out[col] = sum(float(r.get(col, 0.0)) * w for r, w in zip(rows, weights)) / total_w if total_w else 0.0
    return pd.Series(out)


def _derive_batting_rates(s: pd.Series) -> pd.Series:
    singles = s["H"] - s["2B"] - s["3B"] - s["HR"]
    tb = singles + 2 * s["2B"] + 3 * s["3B"] + 4 * s["HR"]
    avg = safe_divide(s["H"], s["AB"])
    obp = safe_divide(s["H"] + s["BB"] + s.get("HBP", 0), s["AB"] + s["BB"] + s.get("HBP", 0) + s.get("SF", 0))
    slg = safe_divide(tb, s["AB"])
    return pd.Series({"AVG": avg, "OBP": obp, "SLG": slg, "OPS": obp + slg})


def _derive_pitching_rates(s: pd.Series) -> pd.Series:
    era = safe_divide(s["ER"] * 9, s["IP"])
    whip = safe_divide(s["H"] + s["BB"], s["IP"])
    return pd.Series({"ERA": era, "WHIP": whip})


def project_player(
    player_name: str,
    prior_three: pd.DataFrame,
    kind: str,
    year: int,
    config: MarcelConfig | None = None,
    age: float = 29,
) -> pd.DataFrame:
    config = config or MarcelConfig()
    if prior_three.empty:
        raise ProjectionError("Expected at least one prior season for projection.")

    if kind == "batting":
        comps = BATTING_COMPONENTS
        reg_pt = config.regression_pa
    else:
        comps = PITCHING_COMPONENTS
        reg_pt = config.regression_ip

    prior_df = prior_three.copy()
    for c in comps:
        if c not in prior_df.columns:
            prior_df[c] = 0.0

    rows = [prior_df.iloc[i] for i in range(min(3, prior_df.shape[0]))]
    weighted = _weighted_row(rows, config.season_weights, comps)

    pt_col = comps[0]
    weighted_pt = float(weighted[pt_col])
    reliability = min(1.0, safe_divide(weighted_pt, config.reliability_scale))

    league_pt = float(prior_df[pt_col].sum())
    league_rates = {c: safe_divide(float(prior_df[c].sum()), league_pt) for c in comps[1:]}

    regressed = weighted.copy()
    regressed[pt_col] = weighted_pt
    for c in comps[1:]:
        player_rate = safe_divide(float(weighted[c]), weighted_pt)
        regressed_rate = safe_divide(player_rate * weighted_pt + league_rates[c] * reg_pt, weighted_pt + reg_pt)
        regressed[c] = regressed_rate * weighted_pt

    growth = config.default_pa_growth if kind == "batting" else config.default_ip_growth
    age_adj = config.age_adjustment_fn(age)
    projected_pt = weighted_pt * growth * age_adj
    pt_scale = safe_divide(projected_pt, weighted_pt)
    regressed *= pt_scale

    if kind == "batting":
        rates = _derive_batting_rates(regressed)
    else:
        rates = _derive_pitching_rates(regressed)

    output = pd.concat([regressed, rates])
    output["Reliability"] = reliability
    output["Name"] = player_name
    output["Year"] = year
    return output.to_frame().T


def project_team(team_df: pd.DataFrame, kind: str, year: int, config: MarcelConfig | None = None) -> pd.DataFrame:
    config = config or MarcelConfig()
    grouped = team_df.groupby("Name", as_index=False)
    projections = [project_player(name, grp.sort_values("Season", ascending=False).head(3), kind, year, config) for name, grp in grouped]
    if not projections:
        raise ProjectionError("No players available to project for this team.")
    return pd.concat(projections, ignore_index=True)
