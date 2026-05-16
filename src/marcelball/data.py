from __future__ import annotations

from pathlib import Path

import pandas as pd

from marcelball.schemas import Kind

CACHE_ROOT = Path(".cache/marcelball")


class DataFetchError(RuntimeError):
    pass


class PlayerLookupError(RuntimeError):
    pass


def _cache_path(kind: Kind, year: int, ext: str = "csv") -> Path:
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    return CACHE_ROOT / f"{kind}_{year}.{ext}"


def _read_cache(kind: Kind, year: int) -> pd.DataFrame | None:
    parquet_path = _cache_path(kind, year, "parquet")
    csv_path = _cache_path(kind, year, "csv")
    if parquet_path.exists():
        return pd.read_parquet(parquet_path)
    if csv_path.exists():
        return pd.read_csv(csv_path)
    return None


def _write_cache(kind: Kind, year: int, df: pd.DataFrame) -> None:
    parquet_path = _cache_path(kind, year, "parquet")
    csv_path = _cache_path(kind, year, "csv")
    try:
        df.to_parquet(parquet_path, index=False)
    except Exception:
        df.to_csv(csv_path, index=False)


def fetch_season_stats(year: int, kind: Kind, use_cache: bool = True) -> pd.DataFrame:
    cached = _read_cache(kind, year) if use_cache else None
    if cached is not None:
        return cached

    try:
        import pybaseball as pyb

        if kind == "batting":
            df = pyb.batting_stats(year)
        else:
            df = pyb.pitching_stats(year)
    except Exception as exc:
        raise DataFetchError(f"Unable to fetch {kind} stats for {year}: {exc}") from exc

    if df is None or df.empty:
        raise DataFetchError(f"No {kind} stats returned for {year}.")

    _write_cache(kind, year, df)
    return df


def lookup_player_ids(name: str) -> pd.DataFrame:
    parts = name.strip().split()
    if len(parts) < 2:
        raise PlayerLookupError("Provide both first and last name.")
    first, last = parts[0], parts[-1]
    try:
        import pybaseball as pyb

        df = pyb.playerid_lookup(last, first)
    except Exception as exc:
        raise PlayerLookupError(f"Failed player lookup for '{name}': {exc}") from exc
    if df.empty:
        raise PlayerLookupError(f"No player found for '{name}'.")
    return df
