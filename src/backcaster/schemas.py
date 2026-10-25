from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

Kind = Literal["batting", "pitching"]
OutputFormat = Literal["cli", "csv", "html"]


@dataclass(frozen=True)
class MarcelConfig:
    """Configuration for pitching projections only.

    Batting uses the fixed population model in backcaster.batters.project_batters.
    """

    season_weights: tuple[float, float, float] = (5.0, 4.0, 3.0)
    regression_ip: float = 200.0
    default_ip_growth: float = 1.0


@dataclass
class ProjectionResult:
    player_name: str
    kind: Kind
    year: int
    projected: pd.DataFrame
    source_years: tuple[int, int, int]
    reliability: float
    meta: dict[str, str] = field(default_factory=dict)
