from collections.abc import Iterable

import pandas as pd
import pytest

from marcelball.marcel import (
    BATTING_COMPONENTS,
    PITCHING_COMPONENTS,
    ProjectionError,
    _compute_baseline_rates,
    _derive_batting_rates,
    _derive_pitching_rates,
    _weighted_row,
    project_player,
    project_team,
)
from marcelball.schemas import MarcelConfig


def _batting_row(
    season: int,
    pa: float,
    ab: float,
    h: float,
    doubles: float,
    triples: float,
    hr: float,
    bb: float,
    so: float,
    hbp: float,
    sf: float,
) -> dict[str, float]:
    return {
        "Season": season,
        "PA": pa,
        "AB": ab,
        "H": h,
        "2B": doubles,
        "3B": triples,
        "HR": hr,
        "BB": bb,
        "SO": so,
        "HBP": hbp,
        "SF": sf,
    }


def _frame(rows: Iterable[dict[str, float]]) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


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


def test_derive_batting_rates_with_zero_denominators() -> None:
    s = pd.Series({"H": 0, "2B": 0, "3B": 0, "HR": 0, "AB": 0, "BB": 0, "HBP": 0, "SF": 0})
    rates = _derive_batting_rates(s)
    assert rates["AVG"] == 0.0
    assert rates["OBP"] == 0.0
    assert rates["SLG"] == 0.0
    assert rates["OPS"] == 0.0


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


def _batting_prior() -> pd.DataFrame:
    return _frame(
        [
            _batting_row(2025, 700, 600, 180, 35, 2, 30, 80, 120, 5, 6),
            _batting_row(2024, 650, 560, 165, 30, 3, 28, 75, 110, 4, 5),
            _batting_row(2023, 620, 540, 155, 28, 4, 25, 70, 108, 4, 4),
        ]
    )


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
    with pytest.raises(ProjectionError, match="at least one"):
        project_player("Nobody", pd.DataFrame(), "batting", 2026)


def test_project_player_batting_with_missing_optional_columns() -> None:
    prior = _batting_prior().drop(columns=["HBP", "SF"])
    result = project_player("Test Hitter", prior, "batting", 2026)
    assert float(result.loc[0, "OBP"]) > 0
    assert "HBP" in result.columns and "SF" in result.columns


def test_project_player_pitching() -> None:
    result = project_player(
        "Test Pitcher", _pitching_prior(), "pitching", 2026, MarcelConfig(regression_ip=100.0)
    )
    assert float(result.loc[0, "ERA"]) > 0
    assert float(result.loc[0, "WHIP"]) > 0


def test_project_player_supplied_league_rates_branch() -> None:
    prior = _batting_prior()
    custom_rates = {c: 0.0 for c in BATTING_COMPONENTS[1:]}
    out = project_player("Test Hitter", prior, "batting", 2026, league_rates=custom_rates)
    assert float(out.loc[0, "PA"]) > 0


def test_project_player_supplied_league_df_branch() -> None:
    prior = _batting_prior()
    league_df = pd.DataFrame([{c: 100.0 for c in BATTING_COMPONENTS}])
    out = project_player("Test Hitter", prior, "batting", 2026, league_df=league_df)
    assert float(out.loc[0, "AVG"]) > 0


def test_project_player_default_prior_df_baseline_branch() -> None:
    prior = _batting_prior()
    out = project_player("Test Hitter", prior, "batting", 2026)
    assert float(out.loc[0, "PA"]) > 0


@pytest.mark.parametrize("age", [28, 34], ids=["age_le_29", "age_gt_29"])
def test_project_player_age_adjustments(age: int) -> None:
    out = project_player("Test Hitter", _batting_prior(), "batting", 2026, age=age)
    assert float(out.loc[0, "PA"]) > 0


def test_project_player_zero_playing_time() -> None:
    prior = pd.DataFrame([{"Season": 2025, **{c: 0.0 for c in BATTING_COMPONENTS}}])
    out = project_player("Zero PT", prior, "batting", 2026)
    assert float(out.loc[0, "PA"]) == 0.0
    assert float(out.loc[0, "Reliability"]) == 0.0


def test_project_player_invalid_kind() -> None:
    with pytest.raises(ProjectionError, match="kind"):
        project_player("Test", _batting_prior(), "fielding", 2026)


def test_project_player_sorts_unsorted_input_before_weighting() -> None:
    sorted_prior = _batting_prior()
    ascending_prior = sorted_prior.sort_values("Season", ascending=True).reset_index(drop=True)

    out_sorted = project_player("Test Hitter", sorted_prior, "batting", 2026)
    out_ascending = project_player("Test Hitter", ascending_prior, "batting", 2026)

    pd.testing.assert_frame_equal(out_sorted, out_ascending)


def test_project_player_rejects_more_than_three_prior_seasons() -> None:
    df = pd.concat(
        [
            _batting_prior(),
            pd.DataFrame(
                [
                    _batting_row(2022, 610, 530, 150, 26, 3, 22, 68, 105, 3, 4)
                ]
            ),
        ],
        ignore_index=True,
    )
    with pytest.raises(ProjectionError, match="at most three"):
        project_player("Test Hitter", df, "batting", 2026)


def test_project_player_rejects_missing_season_values() -> None:
    prior = _batting_prior().copy()
    prior.loc[1, "Season"] = None

    with pytest.raises(ProjectionError, match="non-missing"):
        project_player("Test Hitter", prior, "batting", 2026)


def test_project_player_rejects_non_numeric_season_values() -> None:
    prior = _batting_prior().copy()
    prior["Season"] = prior["Season"].astype("object")
    prior.loc[0, "Season"] = "bad-season"

    with pytest.raises(ProjectionError, match="numeric"):
        project_player("Test Hitter", prior, "batting", 2026)


def test_project_player_uses_stable_sort_for_duplicate_seasons() -> None:
    prior = _frame(
        [
            _batting_row(2025, 600, 500, 150, 30, 2, 20, 70, 110, 3, 4),
            _batting_row(2025, 300, 250, 80, 15, 1, 10, 35, 60, 2, 2),
            _batting_row(2024, 200, 180, 50, 10, 1, 5, 20, 45, 1, 2),
        ]
    )

    out = project_player("Test Hitter", prior, "batting", 2026)
    expected_weighted_pa = (600 * 5 + 300 * 4 + 200 * 3) / 12
    assert float(out.loc[0, "PA"]) == pytest.approx(expected_weighted_pa * 1.006)


def test_project_team_success() -> None:
    p1 = _batting_prior().assign(Name="A")
    p2 = _batting_prior().assign(Name="B")
    team_df = pd.concat([p1, p2], ignore_index=True)
    out = project_team(team_df, "batting", 2026)
    assert sorted(out["Name"].tolist()) == ["A", "B"]


def test_project_team_empty_no_players() -> None:
    empty = pd.DataFrame(columns=["Name", "Season", *BATTING_COMPONENTS])
    with pytest.raises(ProjectionError, match="No players"):
        project_team(empty, "batting", 2026)


def test_project_team_missing_name_season_validation() -> None:
    no_name = _batting_prior()
    with pytest.raises(ProjectionError, match="Name"):
        project_team(no_name, "batting", 2026)

    no_season = _batting_prior().assign(Name="A").drop(columns=["Season"])
    with pytest.raises(ProjectionError, match="Season"):
        project_team(no_season, "batting", 2026)
