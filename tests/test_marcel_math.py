import pandas as pd

from marcelball.marcel import project_player
from marcelball.schemas import MarcelConfig


def test_batting_projection_derives_rates_from_components() -> None:
    df = pd.DataFrame(
        [
            {"Season": 2025, "PA": 700, "AB": 600, "H": 180, "2B": 35, "3B": 2, "HR": 30, "BB": 80, "SO": 120, "HBP": 5, "SF": 6},
            {"Season": 2024, "PA": 650, "AB": 560, "H": 165, "2B": 30, "3B": 3, "HR": 28, "BB": 75, "SO": 110, "HBP": 4, "SF": 5},
            {"Season": 2023, "PA": 620, "AB": 540, "H": 155, "2B": 28, "3B": 4, "HR": 25, "BB": 70, "SO": 108, "HBP": 4, "SF": 4},
        ]
    )
    result = project_player("Test Hitter", df, "batting", 2026, MarcelConfig(regression_pa=300.0))
    assert float(result.loc[0, "AVG"]) > 0
    assert abs(float(result.loc[0, "OPS"]) - (float(result.loc[0, "OBP"]) + float(result.loc[0, "SLG"]))) < 1e-9
    assert 0 <= float(result.loc[0, "Reliability"]) <= 1


def test_pitching_projection_derives_rates_from_components() -> None:
    df = pd.DataFrame(
        [
            {"Season": 2025, "IP": 200, "ER": 65, "H": 170, "HR": 24, "BB": 50, "SO": 220, "BF": 800},
            {"Season": 2024, "IP": 180, "ER": 70, "H": 160, "HR": 25, "BB": 55, "SO": 200, "BF": 760},
            {"Season": 2023, "IP": 210, "ER": 75, "H": 180, "HR": 28, "BB": 60, "SO": 215, "BF": 840},
        ]
    )
    result = project_player("Test Pitcher", df, "pitching", 2026, MarcelConfig(regression_ip=100.0))
    assert float(result.loc[0, "ERA"]) > 0
    assert float(result.loc[0, "WHIP"]) > 0
    assert 0 <= float(result.loc[0, "Reliability"]) <= 1
