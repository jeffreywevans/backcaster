import pandas as pd
import pytest

from backcaster.ages import season_ages


@pytest.mark.parametrize(
    "month,day,expected",
    [(1, 1, 25), (6, 29, 25), (6, 30, 25), (7, 1, 24), (12, 31, 24), (2, 29, 25)],
)
def test_age_on_june_30(month, day, expected):
    people = pd.DataFrame([dict(birthYear=2000, birthMonth=month, birthDay=day)], index=["player"])
    original = people.copy(deep=True)
    result = season_ages(people, 2025)
    assert result.loc["player"] == expected
    pd.testing.assert_frame_equal(people, original)


@pytest.mark.parametrize(
    "birth",
    [
        {"birthYear": 1990},
        {"birthYear": 1990, "birthMonth": 2, "birthDay": 29},
        {"birthYear": 1990, "birthMonth": 6, "birthDay": 31},
        {"birthYear": 1990, "birthMonth": 13, "birthDay": 1},
        {"birthYear": 1990.5, "birthMonth": 1, "birthDay": 1},
        {"birthYear": 1990, "birthMonth": 1.5, "birthDay": 1},
        {"birthYear": "unknown", "birthMonth": 1, "birthDay": 1},
        {"birthYear": float("inf"), "birthMonth": 1, "birthDay": 1},
    ],
)
def test_invalid_or_incomplete_birthdate_is_not_guessed(birth):
    assert season_ages(pd.DataFrame([birth]), 2025).isna().all()
