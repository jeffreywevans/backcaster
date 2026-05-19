from __future__ import annotations

from pathlib import Path

import pandas as pd


def to_cli_table(df: pd.DataFrame) -> str:
    return df.to_string(index=False)


def to_csv(df: pd.DataFrame, out_path: str | Path) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    return out


def to_html(df: pd.DataFrame, out_path: str | Path) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    html = df.to_html(index=False, border=0)
    out.write_text(html, encoding="utf-8")
    return out
