import numpy as np
import pandas as pd
import pytest

from backcaster import batters
from backcaster.batters import EVENTS, _events, _rebaseline, project_batters
from backcaster.marcel import ProjectionError


def history() -> pd.DataFrame:
    rows = []
    for year, pa, hr in [(2024, 600, 60), (2023, 300, 30), (2022, 100, 0)]:
        for player, exposure, homers in [("A", pa, hr), ("B", 1000 - pa, 0)]:
            rows.append(
                dict(
                    PlayerID=player,
                    Name=player,
                    Season=year,
                    PA=exposure,
                    AB=exposure,
                    H=exposure * 0.25,
                    SO=exposure * 0.2,
                    HR=homers,
                    **{"2B": exposure * 0.05, "3B": 0},
                    BB=0,
                    HBP=0,
                    SF=0,
                    SH=0,
                    birthYear=1996,
                    R=exposure * 0.12,
                    RBI=exposure * 0.11,
                    SB=exposure * 0.02,
                    CS=exposure * 0.01,
                    GDP=exposure * 0.03,
                    IBB=0,
                )
            )
    return pd.DataFrame(rows)


def test_exposure_weighted_league_and_playing_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(batters, "_rebaseline", lambda events, pa, target: events)
    result = project_batters(history(), 2025).set_index("PlayerID")
    assert result.loc["A", "PA"] == 530
    # Weighted player PA=4,500; HR=420; league HR/PA=.06/.03/0.
    # Player-specific baseline=(3000*.06+1200*.03+300*0)/4500=.048.
    assert result.loc["A", "HR"] == pytest.approx(530 * (420 + 1200 * 0.048) / 5700)
    assert result.loc["A", "Reliability"] == pytest.approx(4500 / 5700)
    assert result.loc["A", "Age"] == 29


def test_rebaselining_conserves_player_pa_and_league_rates() -> None:
    data = history()
    result = project_batters(data, 2025)
    target = _events(data[data.Season == 2024]).sum() / 1000
    actual = _events(result).sum() / result.PA.sum()
    np.testing.assert_allclose(actual, target, atol=1e-10)
    np.testing.assert_allclose(_events(result).sum(axis=1), result.PA)
    assert (result[EVENTS[1:-1]] >= 0).all().all()


def test_age_changes_skills_without_changing_pa(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(batters, "_rebaseline", lambda events, pa, target: events)
    data = history()
    neutral = project_batters(data, 2025).set_index("PlayerID")
    data.loc[data.PlayerID == "A", "birthYear"] = 1993  # Age 32.
    data.loc[data.PlayerID == "B", "birthYear"] = 2000  # Age 25.
    adjusted = project_batters(data, 2025).set_index("PlayerID")
    assert adjusted.loc["A", "BA"] < neutral.loc["A", "BA"]
    assert adjusted.loc["B", "BA"] > neutral.loc["B", "BA"]
    pd.testing.assert_series_equal(adjusted.PA, neutral.PA)


def test_calendar_weights_missing_season_and_no_future_leakage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(batters, "_rebaseline", lambda events, pa, target: events)
    data = history()
    data = data[~((data.PlayerID == "A") & (data.Season == 2023))]
    future = data[data.Season == 2024].assign(Season=2025, HR=9999)
    result = project_batters(pd.concat([data, future]), 2025).set_index("PlayerID")
    assert result.loc["A", "PA"] == 500
    assert result.loc["A", "Reliability"] == pytest.approx(3300 / 4500)


@pytest.mark.parametrize(
    "case, message",
    [
        ("empty", "No non-pitcher"),
        ("latest", "Latest completed"),
        ("counts", "finite and consistent"),
        ("birth", "birthYear"),
    ],
)
def test_bad_history(case: str, message: str) -> None:
    data = history()
    if case == "empty":
        data = data.iloc[:0]
    elif case == "latest":
        data = data[data.Season != 2024]
    elif case == "counts":
        data["H"] = -1
    else:
        data["birthYear"] = np.nan
    with pytest.raises(ProjectionError, match=message):
        project_batters(data, 2025)


def test_zero_denominators_and_absent_events() -> None:
    data = history()
    data[["H", "2B", "HR", "SO"]] = 0
    data["AB"] = 0
    data["BB"] = data["PA"]
    data["GDP"] = 0
    result = project_batters(data, 2025)
    assert result.BA.isna().all()
    assert result.OBP.eq(1).all()
    assert result.SLG.isna().all()
    assert result.OPS.isna().all()


@pytest.mark.parametrize("sacrifices", [0.0, 10.0])
def test_summarize_preserves_undefined_rates(sacrifices: float) -> None:
    counts = pd.DataFrame([{event: 0.0 for event in EVENTS}])
    counts["SH"] = sacrifices
    original = counts.copy(deep=True)
    result = batters._summarize(counts, pd.Series([sacrifices])).iloc[0]
    assert result[["BA", "OBP", "SLG", "OPS"]].isna().all()
    assert result[["H", "AB", "TB"]].eq(0).all()
    assert result.PA == sacrifices
    pd.testing.assert_frame_equal(counts, original)


def test_rebaseline_nonconvergence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(batters.np, "allclose", lambda *args, **kwargs: False)
    events = pd.DataFrame([{c: 1.0 for c in EVENTS}])
    pa = pd.Series([10.0])
    target = pd.Series({c: 0.1 for c in EVENTS})
    with pytest.raises(ProjectionError, match="did not converge"):
        _rebaseline(events, pa, target)


def test_expanded_schema_and_context_league_totals() -> None:
    data = history()
    result = project_batters(data, 2025)
    expected = "PA,AB,R,H,2B,3B,HR,RBI,SB,CS,BB,SO,BA,OBP,SLG,OPS,TB,GDP,HBP,SH,SF,IBB".split(",")
    assert result.columns.tolist() == ["Name", "Year", "PlayerID", "Age", *expected, "Reliability"]
    latest = data[data.Season == 2024]
    for stat in ["R", "RBI", "SB", "CS", "GDP", "IBB"]:
        assert result[stat].sum() / result.PA.sum() == pytest.approx(
            latest[stat].sum() / latest.PA.sum()
        )
    assert result.IBB.le(result.BB + 1e-10).all()
    assert result.GDP.le(result.AB - result.H - result.SO + 1e-10).all()


def test_total_bases_and_rates_use_unrounded_components_once() -> None:
    from backcaster.batters import _summarize

    counts = pd.DataFrame(
        [
            {
                "1B": 80.0,
                "2B": 20.0,
                "3B": 5.0,
                "HR": 25.0,
                "BB": 50.0,
                "HBP": 5.0,
                "SO": 100.0,
                "OUT": 200.0,
                "SH": 3.0,
                "SF": 7.0,
                "R": 80.0,
                "RBI": 90.0,
                "SB": 20.0,
                "CS": 5.0,
                "GDP": 10.0,
                "IBB": 15.0,
            }
        ]
    )
    result = _summarize(counts, pd.Series([495.0])).iloc[0]
    assert result.H == 130
    assert result.AB == 430
    assert result.TB == 235
    assert result.BA == pytest.approx(130 / 430)
    assert result.OBP == pytest.approx(185 / 492)
    assert result.SLG == pytest.approx(235 / 430)
    assert result.OPS == pytest.approx(185 / 492 + 235 / 430)
    counts[["R", "RBI", "SB", "CS", "GDP", "IBB"]] = [100, 110, 30, 10, 20, 25]
    changed = _summarize(counts, pd.Series([495.0])).iloc[0]
    for stat in ["PA", "AB", "H", "TB", "BA", "OBP", "SLG", "OPS"]:
        assert changed[stat] == result[stat]


def test_stolen_base_regression_hand_calculation() -> None:
    from backcaster.batters import _context_counts, _regress

    data = history()
    data.loc[data.PlayerID == "A", "SB"] = [20, 10, 5]
    data.loc[data.PlayerID == "B", "SB"] = [5, 5, 5]
    events = _events(data)
    counts = events.join(_context_counts(data, events))
    rates, _, _ = _regress(data, counts, 2025)
    # Evidence SB=155, exposure=4500; seasonal league SB rates=.025/.015/.010.
    # Baseline=(3000*.025+1200*.015+300*.010)/4500=96/4500.
    assert rates.loc["A", "SB"] == pytest.approx((155 + 1200 * 96 / 4500) / 5700)


@pytest.mark.parametrize("target, expected", [(0, [0.0, 0.0]), (6, [2.0, 4.0]), (12, [2.0, 10.0])])
def test_bounded_context_rebaselining(target: float, expected: list[float]) -> None:
    from backcaster.batters import _bounded_rebaseline

    actual = _bounded_rebaseline(pd.Series([100.0, 1.0]), target, pd.Series([2.0, 10.0]))
    np.testing.assert_allclose(actual, expected, atol=1e-10)


@pytest.mark.parametrize("target", [-1, 13])
def test_impossible_context_target(target: float) -> None:
    from backcaster.batters import _bounded_rebaseline

    values = pd.Series([1.0, 1.0])
    cap = pd.Series([2.0, 10.0])
    with pytest.raises(ProjectionError, match="event capacity"):
        _bounded_rebaseline(values, target, cap)


@pytest.mark.parametrize(
    "stat,value,message",
    [
        ("R", -1, "finite"),
        ("R", float("inf"), "finite"),
        ("IBB", 1, "IBB must"),
        ("GDP", 1000, "GDP must"),
    ],
)
def test_invalid_context_counts(stat: str, value: float, message: str) -> None:
    data = history()
    data[stat] = value
    with pytest.raises(ProjectionError, match=message):
        project_batters(data, 2025)
