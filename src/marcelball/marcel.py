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


def _compute_baseline_rates(df: pd.DataFrame, comps: list[str]) -> tuple[float, dict[str, float]]:
    pt_col = comps[0]
    present_cols = [c for c in comps if c in df.columns]
    sums = df[present_cols].sum() if present_cols else pd.Series(dtype="float64")
    league_pt = float(sums.get(pt_col, 0.0))
    league_rates = {
        c: safe_divide(float(sums.get(c, 0.0)), league_pt)
        for c in comps[1:]
    }
    return league_pt, league_rates


def _validate_projection_kind(kind: str) -> str:
    if kind not in {"batting", "pitching"}:
        raise ProjectionError(
            f"Invalid kind {kind!r}. Expected one of: 'batting', 'pitching'."
        )
    return kind


def _projection_components(kind: str, config: MarcelConfig) -> tuple[list[str], float]:
    if kind == "batting":
        return BATTING_COMPONENTS, config.regression_pa
    return PITCHING_COMPONENTS, config.regression_ip


def _prepare_prior_df(prior_three: pd.DataFrame, comps: list[str]) -> pd.DataFrame:
    if "Season" not in prior_three.columns:
        raise ProjectionError("Missing required Season column in prior seasons input.")

    season_values = prior_three["Season"]
    if season_values.isna().any():
        raise ProjectionError("Season values must be non-missing in prior seasons input.")

    try:
        season_numeric = pd.to_numeric(season_values, errors="raise")
    except (TypeError, ValueError) as exc:
        raise ProjectionError("Season values must be numeric and consistently typed.") from exc

    prior_df = (
        prior_three.assign(Season=season_numeric)
        .sort_values("Season", ascending=False, kind="mergesort")
        .reset_index(drop=True)
        .copy()
    )

    for c in comps:
        if c not in prior_df.columns:
            prior_df[c] = 0.0
    return prior_df


def project_player(
    player_name: str,
    prior_three: pd.DataFrame,
    kind: str,
    year: int,
    config: MarcelConfig | None = None,
    age: float = 29,
    league_df: pd.DataFrame | None = None,
    league_rates: dict[str, float] | None = None,
) -> pd.DataFrame:
    config = config or MarcelConfig()
    if prior_three.empty:
        raise ProjectionError("Expected at least one prior season for projection.")
    if prior_three.shape[0] > 3:
        raise ProjectionError("Expected at most three prior seasons for projection.")

    kind = _validate_projection_kind(kind)
    comps, reg_pt = _projection_components(kind, config)
    prior_df = _prepare_prior_df(prior_three, comps)

    rows = [prior_df.iloc[i] for i in range(min(3, prior_df.shape[0]))]
    weighted = _weighted_row(rows, config.season_weights, comps)

    pt_col = comps[0]
    weighted_pt = float(weighted[pt_col])
    reliability = min(1.0, safe_divide(weighted_pt, config.reliability_scale))

    if league_rates is None:
        baseline_df = league_df if league_df is not None else prior_df
        _, league_rates = _compute_baseline_rates(baseline_df, comps)

    regressed = weighted.copy()
    regressed[pt_col] = weighted_pt
    for c in comps[1:]:
        regressed_rate = safe_divide(float(weighted[c]) + league_rates[c] * reg_pt, weighted_pt + reg_pt)
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


def project_team(
    team_df: pd.DataFrame,
    kind: str,
    year: int,
    config: MarcelConfig | None = None,
    baseline_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    config = config or MarcelConfig()
    if "Name" not in team_df.columns:
        raise ProjectionError("Missing required Name column in team input.")
    if "Season" not in team_df.columns:
        raise ProjectionError("Missing required Season column in team input.")
    kind = _validate_projection_kind(kind)
    if kind == "batting":
        comps = BATTING_COMPONENTS
    else:
        comps = PITCHING_COMPONENTS
    baseline_source = baseline_df if baseline_df is not None else team_df
    _, baseline_rates = _compute_baseline_rates(baseline_source, comps)
    grouped = team_df.groupby("Name", as_index=False)
    projections = [
        project_player(
            name,
            grp.sort_values("Season", ascending=False).head(3),
            kind,
            year,
            config,
            league_rates=baseline_rates,
        )
        for name, grp in grouped
    ]
    if not projections:
        raise ProjectionError("No players available to project for this team.")
    return pd.concat(projections, ignore_index=True)
