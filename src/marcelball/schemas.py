from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

Kind = Literal["batting", "pitching"]
OutputFormat = Literal["cli", "csv", "html"]


@dataclass(frozen=True)
class MarcelConfig:
    """Configuration knobs for Marcel-style projection."""

    season_weights: tuple[float, float, float] = (5.0, 4.0, 3.0)
    regression_pa: float = 1200.0
    regression_ip: float = 200.0
    age_adjustment_fn: Callable[[float], float] = lambda age: 1.0 + (0.006 if age <= 29 else -0.003)
    reliability_scale: float = 1200.0
    default_pa_growth: float = 1.0
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
