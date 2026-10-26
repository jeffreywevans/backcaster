from __future__ import annotations

import math

import numpy as np
import pandas as pd

from backcaster.ages import season_ages
from backcaster.normalize import safe_divide
from backcaster.schemas import MarcelConfig
from backcaster.stat_columns import PITCHING_EXTRA_COUNTS


class ProjectionError(RuntimeError):
    pass


PITCHING_COMPONENTS = ["IP", "ER", "H", "HR", "BB", "SO", "BF", *PITCHING_EXTRA_COUNTS]


def _pitcher_age(prior: pd.DataFrame, year: int, fallback: float) -> float:
    age = fallback
    if "birthYear" in prior:
        age = float(season_ages(prior.iloc[:1], year).iloc[0])
    if not math.isfinite(age) or not 15 <= age <= 70:
        raise ProjectionError(
            "A valid birthYear or explicit age is required for pitcher aging; birth dates also require valid birthMonth and birthDay."
        )
    return age


def _age_pitching(counts: pd.Series, age: float) -> pd.Series:
    # Equations adapted from Ben Dilday's marcelR, utilities.R and
    # inst/scripts/marcel_data_exporter.R, revision 13a1c7943f5a7317c9c812a28e299c2184060046.
    # Copyright (c) 2017 Ben Dilday, MIT; see THIRD_PARTY_NOTICES.md.
    benefit = 1 / (1 + 0.003 * (age - 29)) if age > 29 else 1 + 0.006 * (29 - age)
    result = counts.copy()
    result[["ER", "H", "HR", "BB", "R", "IBB", "HBP", "BK", "WP"]] /= benefit
    result["SO"] *= benefit
    return result


def _weighted_row(rows: list[pd.Series], weights: tuple[float, ...], cols: list[str]) -> pd.Series:
    total_w = sum(weights[: len(rows)])
    out = {}
    for col in cols:
        out[col] = (
            sum(float(r.get(col, 0.0)) * w for r, w in zip(rows, weights)) / total_w
            if total_w
            else 0.0
        )
    return pd.Series(out)


def _derive_pitching_rates(s: pd.Series) -> pd.Series:
    era = safe_divide(s["ER"] * 9, s["IP"])
    whip = safe_divide(s["H"] + s["BB"], s["IP"])
    decisions = s.get("W", 0) + s.get("L", 0)
    return pd.Series(
        {
            "W-L%": s.get("W", 0) / decisions if decisions else float("nan"),
            "ERA": era,
            "WHIP": whip,
            "H9": safe_divide(s["H"] * 9, s["IP"]),
            "HR9": safe_divide(s.get("HR", 0) * 9, s["IP"]),
            "BB9": safe_divide(s["BB"] * 9, s["IP"]),
            "SO9": safe_divide(s.get("SO", 0) * 9, s["IP"]),
            "SO/W": s.get("SO", 0) / s["BB"] if s["BB"] else float("nan"),
        }
    )


def _compute_baseline_rates(df: pd.DataFrame, comps: list[str]) -> tuple[float, dict[str, float]]:
    pt_col = comps[0]
    present_cols = [c for c in comps if c in df.columns]
    sums = df[present_cols].sum() if present_cols else pd.Series(dtype="float64")
    league_pt = float(sums.get(pt_col, 0.0))
    league_rates = {c: safe_divide(float(sums.get(c, 0.0)), league_pt) for c in comps[1:]}
    return league_pt, league_rates


def _validate_projection_kind(kind: str) -> None:
    if kind != "pitching":
        raise ProjectionError(
            f"Invalid kind {kind!r}. These projections support only 'pitching'; "
            "use backcaster.batters.project_batters for batting projections."
        )


def _prepare_prior_df(
    prior_three: pd.DataFrame, comps: list[str], optional_comps: set[str] | None = None
) -> pd.DataFrame:
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

    optional_comps = optional_comps or set()
    missing_required = [c for c in comps if c not in prior_df.columns and c not in optional_comps]
    if missing_required:
        missing_required_str = ", ".join(sorted(missing_required))
        raise ProjectionError(
            f"Missing required component columns in prior seasons input: {missing_required_str}."
        )

    for c in optional_comps:
        if c in comps and c not in prior_df.columns:
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
    """Project one pitcher; batting uses the population model in project_batters."""
    config = config or MarcelConfig()
    _validate_projection_kind(kind)
    if prior_three.empty:
        raise ProjectionError("Expected at least one prior season for projection.")
    if prior_three.shape[0] > 3:
        raise ProjectionError("Expected at most three prior seasons for projection.")

    comps, reg_pt = PITCHING_COMPONENTS, config.regression_ip
    optional_comps = set(PITCHING_EXTRA_COUNTS)
    prior_df = _prepare_prior_df(prior_three, comps, optional_comps=optional_comps)

    rows = [prior_df.iloc[i] for i in range(min(3, prior_df.shape[0]))]
    calendar_weights: dict[float, float] = dict(
        zip((year - 1, year - 2, year - 3), config.season_weights)
    )
    weights = tuple(calendar_weights.get(float(row["Season"]), 0.0) for row in rows)
    weighted = _weighted_row(rows, weights, comps)

    pt_col = comps[0]
    # Regression uses weighted totals, independently of projected playing time.
    evidence = weighted * sum(weights)
    evidence_pt = float(evidence[pt_col])
    reliability = safe_divide(evidence_pt, evidence_pt + reg_pt)

    if league_rates is None:
        baseline_df = league_df if league_df is not None else prior_df
        _, league_rates = _compute_baseline_rates(baseline_df, comps)

    playing_time = prior_df["Season"].map({year - 1: 0.5, year - 2: 0.1}).fillna(0.0)
    projected_pt = (float((prior_df["IP"] * playing_time).sum()) + 60) * config.default_ip_growth
    regressed = weighted.copy()
    regressed[pt_col] = projected_pt
    for c in comps[1:]:
        regressed_rate = safe_divide(
            float(evidence[c]) + league_rates[c] * reg_pt, evidence_pt + reg_pt
        )
        regressed[c] = regressed_rate * projected_pt

    age = _pitcher_age(prior_df, year, age)
    regressed = _age_pitching(regressed, age)
    rates = _derive_pitching_rates(regressed)

    output = pd.DataFrame([pd.concat([regressed, rates]).to_dict()])
    output["Reliability"] = reliability
    output["ConfidenceTier"] = "core" if reliability >= 0.5 else "low-sample"
    output["Name"] = player_name
    output["Year"] = year
    output["Age"] = float(age)
    return output


def project_team(
    team_df: pd.DataFrame,
    kind: str,
    year: int,
    config: MarcelConfig | None = None,
    baseline_df: pd.DataFrame | None = None,
    age: float = 29,
) -> pd.DataFrame:
    """Project pitchers; age is the shared fallback when birthYear is absent."""
    config = config or MarcelConfig()
    _validate_projection_kind(kind)
    if "Name" not in team_df.columns:
        raise ProjectionError("Missing required Name column in team input.")
    if "Season" not in team_df.columns:
        raise ProjectionError("Missing required Season column in team input.")
    comps = PITCHING_COMPONENTS
    baseline_source = baseline_df if baseline_df is not None else team_df
    _, baseline_rates = _compute_baseline_rates(baseline_source, comps)
    if team_df.empty:
        raise ProjectionError("No players available to project for this team.")
    identity = "PlayerID" if "PlayerID" in team_df.columns else "IDfg"
    keys = team_df[identity].fillna(team_df["Name"]) if identity in team_df else team_df["Name"]
    # Integer groups retain first-appearance ordering and separate duplicate names.
    groups, _ = pd.factorize(keys, sort=False, use_na_sentinel=False)
    prior = _prepare_prior_df(
        team_df.assign(_group=groups), comps, optional_comps=set(PITCHING_EXTRA_COUNTS)
    )
    prior = prior.groupby("_group", sort=False).head(3)
    latest = prior.drop_duplicates("_group").set_index("_group").sort_index()
    if not latest["Name"].map(lambda name: isinstance(name, str)).all():
        raise ProjectionError("Encountered non-string player name in team input.")
    ages = (
        season_ages(latest, year) if "birthYear" in latest else pd.Series(age, index=latest.index)
    ).astype(float)
    if not (np.isfinite(ages) & ages.between(15, 70)).all():
        raise ProjectionError(
            "A valid birthYear or explicit age is required for pitcher aging; birth dates also require valid birthMonth and birthDay."
        )

    weights = (
        prior["Season"]
        .map(dict(zip((year - 1, year - 2, year - 3), config.season_weights)))
        .fillna(0.0)
    )
    weight_sums = weights.groupby(prior["_group"]).sum()
    weighted_counts = prior[comps].astype(float).mul(weights, axis=0)
    grouped = weighted_counts.groupby(prior["_group"])
    # Match scalar arithmetic: a missing component propagates, rather than
    # disappearing in pandas' default skip-NaN sum.
    evidence = grouped.sum().where(grouped.count().eq(grouped.size(), axis=0))
    evidence = evidence.where(weight_sums.ne(0), 0.0, axis=0)
    denominator = evidence["IP"] + config.regression_ip
    output = pd.DataFrame(index=latest.index)
    playing_time = prior["Season"].map({year - 1: 0.5, year - 2: 0.1}).fillna(0.0)
    recent_ip = (prior["IP"] * playing_time).groupby(prior["_group"]).sum()
    output["IP"] = (recent_ip + 60) * config.default_ip_growth
    for column in comps[1:]:
        rate = _pitching_ratio(
            evidence[column] + baseline_rates[column] * config.regression_ip, denominator
        )
        output[column] = rate * output["IP"]

    # Same marcelR skill adjustment as the single-player reference calculation.
    benefit = pd.Series(
        np.where(ages > 29, 1 / (1 + 0.003 * (ages - 29)), 1 + 0.006 * (29 - ages)),
        index=ages.index,
    )
    harmful = ["ER", "H", "HR", "BB", "R", "IBB", "HBP", "BK", "WP"]
    output[harmful] = output[harmful].div(benefit, axis=0)
    output["SO"] *= benefit
    decisions = output["W"] + output["L"]
    output["W-L%"] = output["W"].div(decisions.replace(0, np.nan))
    output["ERA"] = _pitching_ratio(output["ER"] * 9, output["IP"])
    output["WHIP"] = _pitching_ratio(output["H"] + output["BB"], output["IP"])
    for rate_column, count in [("H9", "H"), ("HR9", "HR"), ("BB9", "BB"), ("SO9", "SO")]:
        output[rate_column] = _pitching_ratio(output[count] * 9, output["IP"])
    output["SO/W"] = output["SO"].div(output["BB"].replace(0, np.nan))
    output["Reliability"] = _pitching_ratio(evidence["IP"], denominator)
    output["ConfidenceTier"] = np.where(output["Reliability"] >= 0.5, "core", "low-sample")
    output["Name"] = latest["Name"]
    output["Year"] = year
    output["Age"] = ages
    if "PlayerID" in latest:
        output["PlayerID"] = latest["PlayerID"]
    return output.reset_index(drop=True)


def _pitching_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Vector equivalent of safe_divide, including a zero numerator result at 0 IP."""
    nonzero = denominator.ne(0)
    return numerator.div(denominator.where(nonzero, 1)).where(nonzero, 0.0)
