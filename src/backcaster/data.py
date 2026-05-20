from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Iterable
from numbers import Number
from pathlib import Path
from typing import SupportsInt, cast

import pandas as pd

from backcaster.schemas import Kind

CACHE_ROOT = Path.home() / ".cache" / "backcaster"
VALID_KINDS: tuple[Kind, ...] = ("batting", "pitching")

LOGGER = logging.getLogger(__name__)


class DataFetchError(RuntimeError):
    pass


class PlayerLookupError(RuntimeError):
    pass


def _normalize_name(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _clean_name_value(row: pd.Series, key: str) -> str:
    value = row.get(key)
    return str(value).strip() if pd.notna(value) else ""


def _candidate_full_names(row: pd.Series) -> set[str]:
    names: set[str] = set()
    first = _clean_name_value(row, "name_first")
    last = _clean_name_value(row, "name_last")
    given = _clean_name_value(row, "name_given")
    if first and last:
        names.add(_normalize_name(f"{first} {last}"))
    if given:
        names.add(_normalize_name(given))
    return names


def _to_int_or_none(value: object) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (Number, str, bytes, bytearray)):
        try:
            return int(cast(SupportsInt | str | bytes | bytearray, value))
        except (TypeError, ValueError):
            return None
    return None


def _format_numeric_or_unknown(value: object) -> str:
    as_int = _to_int_or_none(value)
    return str(as_int) if as_int is not None else "?"


def _filter_candidates_by_name(requested_name: str, lookup_df: pd.DataFrame) -> pd.DataFrame:
    def _normalized_name_column(column_name: str) -> pd.Series:
        if column_name not in lookup_df.columns:
            return pd.Series("", index=lookup_df.index, dtype="object")
        return lookup_df[column_name].astype("string").fillna("").str.strip()

    first_names = _normalized_name_column("name_first")
    last_names = _normalized_name_column("name_last")
    given_names = _normalized_name_column("name_given")

    full_names = (first_names + " " + last_names).str.strip().map(_normalize_name)
    given_names = given_names.map(_normalize_name)

    has_full_name = first_names.ne("") & last_names.ne("")
    name_mask = (has_full_name & full_names.eq(requested_name)) | given_names.eq(requested_name)
    return lookup_df[name_mask] if name_mask.any() else lookup_df


def _overlaps_year_window(row: pd.Series, start_year: int, end_year: int) -> bool:
    first = _to_int_or_none(row.get("mlb_played_first"))
    last = _to_int_or_none(row.get("mlb_played_last"))
    if first is None and last is None:
        return True
    if first is None:
        return start_year <= last
    if last is None:
        return end_year >= first
    return not (last < start_year or first > end_year)


def _filter_candidates_by_years(candidates: pd.DataFrame, years: list[int]) -> pd.DataFrame:
    has_year_cols = {"mlb_played_first", "mlb_played_last"}.issubset(candidates.columns)
    if not years or not has_year_cols:
        return candidates
    start_year, end_year = min(years), max(years)
    window_mask = candidates.apply(
        lambda row: _overlaps_year_window(row, start_year, end_year), axis=1
    )
    return candidates[window_mask]


def _format_candidate_detail(row: pd.Series) -> str:
    given = _clean_name_value(row, "name_given")
    first_name = _clean_name_value(row, "name_first")
    last_name = _clean_name_value(row, "name_last")
    label = given or f"{first_name} {last_name}".strip() or "Unknown Player"
    fg = _format_numeric_or_unknown(row.get("key_fangraphs"))
    start = _format_numeric_or_unknown(row.get("mlb_played_first"))
    end = _format_numeric_or_unknown(row.get("mlb_played_last"))
    return f"{label} (key_fangraphs={fg}, MLB={start}-{end})"


def resolve_player_lookup(
    name: str, lookup_df: pd.DataFrame, target_years: Iterable[int]
) -> pd.Series:
    if lookup_df.empty:
        raise PlayerLookupError(f"No player found for '{name}'.")

    requested = _normalize_name(name)
    candidates = _filter_candidates_by_name(requested, lookup_df)

    years = sorted({int(y) for y in target_years})
    candidates = _filter_candidates_by_years(candidates, years)

    if len(candidates) == 1:
        return candidates.iloc[0]

    if len(candidates) == 0:
        raise PlayerLookupError(f"No player found for '{name}' in seasons {years}.")

    details = [_format_candidate_detail(row) for _, row in candidates.iterrows()]

    raise PlayerLookupError(
        f"Duplicate player match for '{name}'. Candidates: " + "; ".join(details)
    )


def _cache_path(kind: Kind, year: int, ext: str = "csv") -> Path:
    if kind not in VALID_KINDS:
        expected = ", ".join(repr(value) for value in VALID_KINDS)
        raise ValueError(f"Invalid kind {kind!r}. Expected one of: {expected}.")
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    return CACHE_ROOT / f"{kind}_{year}.{ext}"


def _read_cache(kind: Kind, year: int) -> pd.DataFrame | None:
    parquet_path = _cache_path(kind, year, "parquet")
    csv_path = _cache_path(kind, year, "csv")

    if parquet_path.exists():
        try:
            return pd.read_parquet(parquet_path)
        except Exception as exc:
            LOGGER.warning(
                "Parquet cache read failed for %s %s at %s; falling back to CSV if available: %s",
                kind,
                year,
                parquet_path,
                exc,
            )

    if csv_path.exists():
        return pd.read_csv(csv_path)
    return None


def _atomic_write_frame(
    df: pd.DataFrame,
    target_path: Path,
    writer: Callable[[pd.DataFrame, Path], None],
) -> None:
    tmp_path = target_path.with_suffix(f"{target_path.suffix}.{uuid.uuid4().hex}.tmp")
    try:
        writer(df, tmp_path)
        tmp_path.replace(target_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _write_cache(kind: Kind, year: int, df: pd.DataFrame) -> None:
    parquet_path = _cache_path(kind, year, "parquet")
    csv_path = _cache_path(kind, year, "csv")

    try:
        _atomic_write_frame(
            df, parquet_path, lambda frame, path: frame.to_parquet(path, index=False)
        )
    except Exception as exc:
        LOGGER.warning(
            "Parquet cache write failed for %s %s at %s; falling back to CSV: %s",
            kind,
            year,
            parquet_path,
            exc,
        )
        _atomic_write_frame(df, csv_path, lambda frame, path: frame.to_csv(path, index=False))


def fetch_season_stats(year: int, kind: Kind, use_cache: bool = True) -> pd.DataFrame:
    if not isinstance(kind, str) or kind not in ("batting", "pitching"):
        raise DataFetchError(f"Invalid kind {kind!r}. Expected one of: 'batting', 'pitching'.")

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
