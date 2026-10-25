from collections.abc import Callable

import pandas as pd
import pytest

from backcaster.marcel import (
    PITCHING_COMPONENTS,
    ProjectionError,
    _compute_baseline_rates,
    _derive_pitching_rates,
    _weighted_row,
    project_player,
    project_team,
)
from backcaster.schemas import MarcelConfig


def test_weighted_row_with_one_row() -> None:
    row = pd.Series({"PA": 300, "AB": 250})
    out = _weighted_row([row], (5.0, 4.0, 3.0), ["PA", "AB"])
    assert float(out["PA"]) == 300.0
    assert float(out["AB"]) == 250.0


def test_weighted_row_with_two_rows() -> None:
    r1 = pd.Series({"PA": 300, "AB": 250})
    r2 = pd.Series({"PA": 100, "AB": 80})
    out = _weighted_row([r1, r2], (5.0, 4.0, 3.0), ["PA", "AB"])
    assert out["PA"] == pytest.approx((300 * 5 + 100 * 4) / 9)
    assert out["AB"] == pytest.approx((250 * 5 + 80 * 4) / 9)


def test_weighted_row_with_three_rows() -> None:
    r1 = pd.Series({"PA": 300})
    r2 = pd.Series({"PA": 200})
    r3 = pd.Series({"PA": 100})
    out = _weighted_row([r1, r2, r3], (5.0, 4.0, 3.0), ["PA"])
    assert out["PA"] == pytest.approx((300 * 5 + 200 * 4 + 100 * 3) / 12)


def test_weighted_row_with_zero_total_weight() -> None:
    row = pd.Series({"PA": 300, "AB": 250})
    out = _weighted_row([row], (0.0, 0.0, 0.0), ["PA", "AB"])
    assert out["PA"] == 0.0
    assert out["AB"] == 0.0


def test_derive_pitching_rates_with_zero_ip() -> None:
    s = pd.Series({"ER": 10, "H": 20, "BB": 5, "IP": 0})
    rates = _derive_pitching_rates(s)
    assert rates["ERA"] == 0.0
    assert rates["WHIP"] == 0.0


def test_compute_baseline_rates_with_full_columns() -> None:
    df = pd.DataFrame(
        [
            {"PA": 100, "AB": 80, "H": 20},
            {"PA": 200, "AB": 160, "H": 40},
        ]
    )
    league_pt, rates = _compute_baseline_rates(df, ["PA", "AB", "H"])
    assert league_pt == 300.0
    assert rates["AB"] == pytest.approx(240 / 300)
    assert rates["H"] == pytest.approx(60 / 300)


def test_compute_baseline_rates_with_missing_columns() -> None:
    df = pd.DataFrame(
        [
            {"PA": 100, "AB": 80},
            {"PA": 200, "AB": 160},
        ]
    )
    league_pt, rates = _compute_baseline_rates(df, ["PA", "AB", "H"])
    assert league_pt == 300.0
    assert rates["AB"] == pytest.approx(240 / 300)
    assert rates["H"] == 0.0


def test_compute_baseline_rates_with_no_present_columns() -> None:
    df = pd.DataFrame([{"X": 1}, {"X": 2}])
    league_pt, rates = _compute_baseline_rates(df, ["PA", "AB", "H"])
    assert league_pt == 0.0
    assert rates["AB"] == 0.0
    assert rates["H"] == 0.0


def _pitching_prior() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Season": 2025,
                "IP": 200,
                "ER": 65,
                "H": 170,
                "HR": 24,
                "BB": 50,
                "SO": 220,
                "BF": 800,
            },
            {
                "Season": 2024,
                "IP": 180,
                "ER": 70,
                "H": 160,
                "HR": 25,
                "BB": 55,
                "SO": 200,
                "BF": 760,
            },
            {
                "Season": 2023,
                "IP": 210,
                "ER": 75,
                "H": 180,
                "HR": 28,
                "BB": 60,
                "SO": 215,
                "BF": 840,
            },
        ]
    )


def test_project_player_empty_input() -> None:
    prior = pd.DataFrame()
    with pytest.raises(ProjectionError, match="at least one"):
        project_player("Nobody", prior, "pitching", 2026)


def test_project_player_pitching() -> None:
    result = project_player(
        "Test Pitcher", _pitching_prior(), "pitching", 2026, MarcelConfig(regression_ip=100.0)
    )
    assert float(result.loc[0, "ERA"]) > 0
    assert float(result.loc[0, "WHIP"]) > 0


@pytest.mark.parametrize("scope", ["player", "team"])
def test_projection_preserves_numeric_dtypes(scope: str) -> None:
    prior = _pitching_prior()
    if scope == "player":
        result = project_player("Pitcher", prior, "pitching", 2026)
    else:
        history = pd.concat([prior.assign(Name=name) for name in ["A", "B"]], ignore_index=True)
        result = project_team(history, "pitching", 2026)
    numeric_columns = [column for column in result if column != "Name"]
    assert all(pd.api.types.is_numeric_dtype(result[column]) for column in numeric_columns)
    assert result["Name"].map(lambda name: isinstance(name, str)).all()
    assert result["IP"].sum() == pytest.approx(len(result) * (0.5 * 200 + 0.1 * 180 + 60))
    assert result["Year"].eq(2026).all()


def test_project_player_supplied_league_rates_branch() -> None:
    prior = _pitching_prior()
    custom_rates = {c: 0.0 for c in PITCHING_COMPONENTS[1:]}
    out = project_player("Test Pitcher", prior, "pitching", 2026, league_rates=custom_rates)
    assert float(out.loc[0, "IP"]) > 0


def test_project_player_supplied_league_df_branch() -> None:
    prior = _pitching_prior()
    league_df = pd.DataFrame([{c: 100.0 for c in PITCHING_COMPONENTS}])
    out = project_player("Test Pitcher", prior, "pitching", 2026, league_df=league_df)
    assert float(out.loc[0, "ERA"]) > 0


def test_project_player_default_prior_df_baseline_branch() -> None:
    prior = _pitching_prior()
    out = project_player("Test Pitcher", prior, "pitching", 2026)
    assert float(out.loc[0, "IP"]) > 0


def test_project_player_zero_history_uses_playing_time_allowance() -> None:
    prior = pd.DataFrame([{"Season": 2025, **{c: 0.0 for c in PITCHING_COMPONENTS}}])
    out = project_player("Zero PT", prior, "pitching", 2026)
    assert float(out.loc[0, "IP"]) == 60.0
    assert float(out.loc[0, "Reliability"]) == 0.0


def test_project_player_invalid_kind() -> None:
    prior = _pitching_prior()
    with pytest.raises(ProjectionError, match="kind"):
        project_player("Test", prior, "fielding", 2026)


def test_project_player_sorts_unsorted_input_before_weighting() -> None:
    sorted_prior = _pitching_prior()
    ascending_prior = sorted_prior.sort_values("Season", ascending=True).reset_index(drop=True)

    out_sorted = project_player("Test Pitcher", sorted_prior, "pitching", 2026)
    out_ascending = project_player("Test Pitcher", ascending_prior, "pitching", 2026)

    pd.testing.assert_frame_equal(out_sorted, out_ascending)


def test_project_player_rejects_more_than_three_prior_seasons() -> None:
    df = pd.concat(
        [
            _pitching_prior(),
            _pitching_prior().iloc[[0]].assign(Season=2022),
        ],
        ignore_index=True,
    )
    with pytest.raises(ProjectionError, match="at most three"):
        project_player("Test Pitcher", df, "pitching", 2026)


def test_project_player_rejects_missing_season_column() -> None:
    prior = _pitching_prior().drop(columns=["Season"])

    with pytest.raises(ProjectionError, match="Missing required Season column"):
        project_player("Test Pitcher", prior, "pitching", 2026)


def test_project_player_allows_missing_optional_pitching_components() -> None:
    prior = _pitching_prior().drop(columns=["HBP", "WP"], errors="ignore")

    out = project_player("Test Pitcher", prior, "pitching", 2026)
    assert float(out.loc[0, "IP"]) > 0


def test_project_player_rejects_missing_required_component_columns() -> None:
    prior = _pitching_prior().drop(columns=["IP", "H"])

    with pytest.raises(ProjectionError, match="Missing required component columns"):
        project_player("Test Pitcher", prior, "pitching", 2026)


def test_project_player_rejects_missing_season_values() -> None:
    prior = _pitching_prior().copy()
    prior.loc[1, "Season"] = None

    with pytest.raises(ProjectionError, match="non-missing"):
        project_player("Test Pitcher", prior, "pitching", 2026)


def test_project_player_rejects_non_numeric_season_values() -> None:
    prior = _pitching_prior().copy()
    prior["Season"] = prior["Season"].astype("object")
    prior.loc[0, "Season"] = "bad-season"

    with pytest.raises(ProjectionError, match="numeric"):
        project_player("Test Pitcher", prior, "pitching", 2026)


@pytest.mark.parametrize(
    ("kind", "prior_factory", "names", "required_cols"),
    [
        ("pitching", _pitching_prior, ["Pitcher A", "Pitcher B"], {"IP", "ERA", "WHIP"}),
    ],
)
def test_project_team_success(
    kind: str, prior_factory: Callable[[], pd.DataFrame], names: list[str], required_cols: set[str]
) -> None:
    team_df = pd.concat([prior_factory().assign(Name=name) for name in names], ignore_index=True)
    out = project_team(team_df, kind, 2026)
    assert sorted(out["Name"].tolist()) == sorted(names)
    assert required_cols.issubset(out.columns)


def test_project_team_groups_by_idfg_when_available() -> None:
    base = _pitching_prior().assign(Name="Same Name")
    player_a = base.assign(IDfg=101)
    player_b = base.assign(IDfg=202)
    team_df = pd.concat([player_a, player_b], ignore_index=True)

    out = project_team(team_df, "pitching", 2026)

    assert out.shape[0] == 2
    assert out["Name"].tolist() == ["Same Name", "Same Name"]


def test_project_team_empty_no_players() -> None:
    empty = pd.DataFrame(columns=["Name", "Season", *PITCHING_COMPONENTS])
    with pytest.raises(ProjectionError, match="No players"):
        project_team(empty, "pitching", 2026)


def test_project_team_missing_name_season_validation() -> None:
    no_name = _pitching_prior()
    with pytest.raises(ProjectionError, match="Name"):
        project_team(no_name, "pitching", 2026)

    no_season = _pitching_prior().assign(Name="A").drop(columns=["Season"])
    with pytest.raises(ProjectionError, match="Season"):
        project_team(no_season, "pitching", 2026)


def test_project_team_rejects_non_string_name() -> None:
    invalid_name_df = _pitching_prior().assign(Name=101)
    with pytest.raises(ProjectionError, match="non-string player name"):
        project_team(invalid_name_df, "pitching", 2026)


def test_pitching_regression_and_reliability_use_innings_evidence() -> None:
    prior = pd.DataFrame(
        [
            {
                "Season": season,
                "IP": 180,
                "ER": 60,
                "H": 150,
                "HR": 20,
                "BB": 50,
                "SO": 200,
                "BF": 750,
            }
            for season in [2024, 2023, 2022]
        ]
    )
    rates = {column: 0.0 for column in PITCHING_COMPONENTS[1:]}
    rates["ER"] = 0.5  # League ERA 4.50, observed player ERA 3.00.
    result = project_player("Starter", prior, "pitching", 2025, league_rates=rates)
    # 2,160 weighted IP, 720 weighted ER, plus 200 IP at 0.5 ER/IP.
    assert float(result.loc[0, "ERA"]) == pytest.approx(9 * (720 + 100) / (2160 + 200))
    assert float(result.loc[0, "Reliability"]) == pytest.approx(2160 / 2360)


@pytest.mark.parametrize("age, factor", [(25, 1.024), (29, 1.0), (34, 1 / 1.015)])
def test_pitcher_age_curve_changes_rates_not_opportunities(age: int, factor: float) -> None:
    neutral = project_player("Pitcher", _pitching_prior(), "pitching", 2026, age=29).iloc[0]
    result = project_player("Pitcher", _pitching_prior(), "pitching", 2026, age=age).iloc[0]
    assert result["IP"] == pytest.approx(neutral["IP"])
    assert result["BF"] == pytest.approx(neutral["BF"])
    assert result["Reliability"] == pytest.approx(neutral["Reliability"])
    for stat in ["ER", "H", "HR", "BB", "ERA", "WHIP"]:
        assert result[stat] == pytest.approx(neutral[stat] / factor)
    assert result["SO"] == pytest.approx(neutral["SO"] * factor)
    assert result["Age"] == age


def test_pitcher_birth_year_overrides_default_age() -> None:
    prior = _pitching_prior().assign(birthYear=1992)
    actual = project_player("Pitcher", prior, "pitching", 2026)
    expected = project_player("Pitcher", _pitching_prior(), "pitching", 2026, age=34)
    pd.testing.assert_frame_equal(actual, expected)


@pytest.mark.parametrize("birth", [float("nan"), float("inf"), "unknown", 1800, 2025])
def test_pitcher_invalid_birth_year(birth: object) -> None:
    prior = _pitching_prior().assign(birthYear=birth)
    with pytest.raises(ProjectionError, match="valid birthYear"):
        project_player("Pitcher", prior, "pitching", 2026)


def test_pitcher_missing_year_keeps_calendar_weights() -> None:
    prior = _pitching_prior()
    prior = prior[prior.Season != 2024]
    result = project_player("Pitcher", prior, "pitching", 2026, age=29).iloc[0]
    assert result["IP"] == pytest.approx(0.5 * 200 + 60)
    assert result["Reliability"] == pytest.approx(1630 / 1830)


def test_pitcher_future_season_has_no_evidence() -> None:
    prior = _pitching_prior().iloc[[0]].assign(Season=2026)
    result = project_player("Pitcher", prior, "pitching", 2026, age=29).iloc[0]
    assert result["IP"] == 60
    assert result["Reliability"] == 0


def test_expanded_pitching_rates_use_true_innings_and_unrounded_counts() -> None:
    row = pd.Series(
        dict(IP=161 + 1 / 3, W=11.0, L=10.0, ER=69.0, H=158.0, HR=18.0, BB=50.0, SO=175.0)
    )
    rates = _derive_pitching_rates(row)
    assert rates["W-L%"] == pytest.approx(11 / 21)
    assert rates["ERA"] == pytest.approx(69 * 27 / 484)
    assert rates["WHIP"] == pytest.approx(208 * 3 / 484)
    for stat, count in [("H9", 158), ("HR9", 18), ("BB9", 50), ("SO9", 175)]:
        assert rates[stat] == pytest.approx(count * 27 / 484)
    assert rates["SO/W"] == 3.5


def test_undefined_pitching_decisions_and_walk_ratio() -> None:
    row = pd.Series(dict(IP=1.0, ER=0.0, H=0.0, BB=0.0, SO=3.0, W=0.0, L=0.0))
    rates = _derive_pitching_rates(row)
    assert pd.isna(rates["W-L%"])
    assert pd.isna(rates["SO/W"])
    assert rates["SO9"] == 27


@pytest.mark.parametrize("kind", ["batting", "fielding"])
def test_legacy_projection_entrypoints_reject_non_pitching(kind: str) -> None:
    prior = _pitching_prior().assign(Name="Player")
    for project in [
        lambda: project_player("Player", prior, kind, 2026),
        lambda: project_team(prior, kind, 2026),
    ]:
        with pytest.raises(ProjectionError, match="project_batters"):
            project()


def test_pitching_config_controls_evidence_regression_and_playing_time() -> None:
    prior = _pitching_prior()
    config = MarcelConfig(
        season_weights=(2.0, 1.0, 0.0), regression_ip=100.0, default_ip_growth=0.5
    )
    rates = {column: 0.0 for column in PITCHING_COMPONENTS[1:]}
    rates["ER"] = 0.5
    result = project_player("Pitcher", prior, "pitching", 2026, config, league_rates=rates).iloc[0]
    assert result.IP == pytest.approx((0.5 * 200 + 0.1 * 180 + 60) * 0.5)
    assert result.Reliability == pytest.approx(580 / 680)
    assert result.ERA == pytest.approx(9 * (2 * 65 + 70 + 100 * 0.5) / 680)


def _scalar_team_reference(
    history: pd.DataFrame, config: MarcelConfig, baseline: pd.DataFrame
) -> pd.DataFrame:
    _, rates = _compute_baseline_rates(baseline, PITCHING_COMPONENTS)
    identity = "PlayerID" if "PlayerID" in history else "IDfg"
    keys = history[identity].fillna(history.Name) if identity in history else history.Name
    rows = []
    for _, group in history.groupby(keys, sort=False, dropna=False):
        prior = group.sort_values("Season", ascending=False, kind="stable").head(3)
        result = project_player(
            prior.Name.iloc[0], prior, "pitching", 2026, config, league_rates=rates
        )
        if "PlayerID" in prior:
            result["PlayerID"] = prior.PlayerID.iloc[0]
        rows.append(result)
    return pd.concat(rows, ignore_index=True)


@pytest.mark.parametrize("identity", ["PlayerID", "IDfg", None])
@pytest.mark.parametrize("birth_years", [True, False])
@pytest.mark.parametrize(
    "config",
    [
        MarcelConfig(),
        MarcelConfig(season_weights=(3.0, 2.0, 1.0), regression_ip=75.0, default_ip_growth=0.8),
        MarcelConfig(season_weights=(0.0, 0.0, 0.0), regression_ip=0.0),
    ],
)
def test_vectorized_pitching_matches_scalar_reference(
    identity: str | None, birth_years: bool, config: MarcelConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    pieces = []
    for player, age in enumerate([25, 29, 34, 70, 15, 35]):
        prior = _pitching_prior().assign(Name="Same Name" if player < 2 else f"Pitcher {player}")
        if identity:
            prior[identity] = None if player == 5 else f"id{player}"
        if birth_years:
            prior["birthYear"] = 2026 - age
        for column in PITCHING_COMPONENTS:
            if column in prior:
                prior[column] *= 1 + player * 0.1
        if player == 0:
            prior.loc[0, "ER"] = float("nan")
        elif player == 1:
            prior = prior[prior.Season != 2024]
        elif player == 2:
            prior[[c for c in PITCHING_COMPONENTS if c in prior]] = 0.0
        elif player == 3:
            prior["BB"] = 0.0
        elif player == 4:
            prior = pd.concat([prior.iloc[[0]].assign(Season=2026), prior], ignore_index=True)
        else:
            prior = pd.concat([prior.iloc[[0]], prior], ignore_index=True)
        pieces.append(prior)
    history = pd.concat(pieces, ignore_index=True).sample(frac=1, random_state=42)
    baseline = _pitching_prior().assign(W=0.0, L=0.0)
    original = history.copy(deep=True)
    expected = _scalar_team_reference(history, config, baseline)

    def forbidden(*args, **kwargs):
        raise AssertionError("team projection invoked scalar project_player")

    monkeypatch.setattr("backcaster.marcel.project_player", forbidden)
    actual = project_team(history, "pitching", 2026, config, baseline_df=baseline)
    pd.testing.assert_frame_equal(actual, expected, rtol=1e-12, atol=1e-12)
    pd.testing.assert_frame_equal(history, original)


@pytest.mark.parametrize("birth", [float("nan"), float("inf"), "unknown", 1800, 2025])
def test_vectorized_pitching_rejects_invalid_age(birth: object) -> None:
    prior = _pitching_prior().assign(Name="Pitcher", birthYear=birth)
    with pytest.raises(ProjectionError, match="valid birthYear"):
        project_team(prior, "pitching", 2026)


@pytest.mark.parametrize(
    "seasons, innings, expected",
    [
        ([2025], [180.0], 150.0),
        ([2024], [180.0], 78.0),
        ([2023], [180.0], 60.0),
        ([2025, 2024, 2023], [181.0, 185.0, 524 / 3], 169.0),
        ([2025, 2023], [180.0, 210.0], 150.0),
    ],
)
def test_pitcher_calendar_playing_time_decay(
    seasons: list[int], innings: list[float], expected: float
) -> None:
    prior = _pitching_prior().iloc[: len(seasons)].copy()
    prior["Season"] = seasons
    prior["IP"] = innings
    for config in [MarcelConfig(), MarcelConfig(season_weights=(1.0, 1.0, 1.0))]:
        scalar = project_player("Pitcher", prior, "pitching", 2026, config).iloc[0]
        batch = project_team(prior.assign(Name="Pitcher"), "pitching", 2026, config).iloc[0]
        assert scalar.IP == pytest.approx(expected)
        assert batch.IP == pytest.approx(expected)
        for stat in ["ERA", "WHIP", "Reliability"]:
            assert scalar[stat] == pytest.approx(batch[stat])


def test_pitcher_playing_time_scales_counts_without_changing_rates() -> None:
    prior = _pitching_prior()
    normal = project_team(prior.assign(Name="Pitcher"), "pitching", 2026).iloc[0]
    scaled = project_team(
        prior.assign(Name="Pitcher"), "pitching", 2026, MarcelConfig(default_ip_growth=0.5)
    ).iloc[0]
    for column in PITCHING_COMPONENTS:
        assert scaled[column] == pytest.approx(normal[column] * 0.5)
    for column in ["ERA", "WHIP", "H9", "HR9", "BB9", "SO9", "Reliability"]:
        assert scaled[column] == pytest.approx(normal[column])
