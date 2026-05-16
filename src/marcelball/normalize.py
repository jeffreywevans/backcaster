from __future__ import annotations

import pandas as pd


def numeric_columns(df: pd.DataFrame, exclude: set[str] | None = None) -> list[str]:
    exclude = exclude or set()
    return [c for c in df.columns if c not in exclude and pd.api.types.is_numeric_dtype(df[c])]


def safe_divide(numerator: float, denominator: float) -> float:
    return 0.0 if denominator == 0 else float(numerator) / float(denominator)
