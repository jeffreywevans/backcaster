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
    assert adjusted.loc["A", "AVG"] < neutral.loc["A", "AVG"]
    assert adjusted.loc["B", "AVG"] > neutral.loc["B", "AVG"]
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
    result = project_batters(data, 2025)
    assert result.AVG.eq(0).all()
    assert result.OBP.eq(1).all()
    assert result.SLG.eq(0).all()


def test_rebaseline_nonconvergence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(batters.np, "allclose", lambda *args, **kwargs: False)
    events = pd.DataFrame([{c: 1.0 for c in EVENTS}])
    pa = pd.Series([10.0])
    target = pd.Series({c: 0.1 for c in EVENTS})
    with pytest.raises(ProjectionError, match="did not converge"):
        _rebaseline(events, pa, target)
