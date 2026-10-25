from pathlib import Path

import pandas as pd
import pytest

from backcaster.data import DataLoadError
from backcaster.eligibility import read_eligibility


def test_snapshot_selects_exact_target_year_and_date(tmp_path: Path) -> None:
    path = tmp_path / "eligibility.csv"
    pd.DataFrame(
        [
            dict(PlayerID=" tiny ", Year=2025, AsOf="2025-01-14", Eligible="TRUE", Team="BOS"),
            dict(PlayerID="retired", Year=2025, AsOf="2025-01-14", Eligible="false", Team=""),
            dict(PlayerID="tiny", Year=2025, AsOf="2025-02-01", Eligible="false", Team=""),
            dict(PlayerID="tiny", Year=2026, AsOf="2025-01-14", Eligible="false", Team=""),
        ]
    ).to_csv(path, index=False)
    snapshot = read_eligibility(path, 2025, "2025-01-14")
    assert snapshot.index.tolist() == ["tiny", "retired"]
    assert snapshot.Eligible.tolist() == [True, False]
    assert snapshot.loc["tiny", "Team"] == "BOS"


@pytest.mark.parametrize("as_of", ["January 14", "20250114", "2025-02-30"])
def test_snapshot_rejects_invalid_date(tmp_path: Path, as_of: str) -> None:
    path = tmp_path / "unused.csv"
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        read_eligibility(path, 2025, as_of)


@pytest.mark.parametrize(
    "case, message",
    [
        ("unreadable", "Unable to read"),
        ("missing", "missing columns"),
        ("date", "no rows"),
        ("year", "no rows"),
        ("empty_id", "nonempty"),
        ("blank_id", "nonempty"),
        ("duplicate", "Duplicate PlayerID"),
        ("decision", "true or false"),
        ("missing_decision", "true or false"),
    ],
)
def test_snapshot_rejects_invalid_data(tmp_path: Path, case: str, message: str) -> None:
    path = tmp_path / "eligibility.csv"
    rows = pd.DataFrame([dict(PlayerID="tiny", Year=2025, AsOf="2025-01-14", Eligible="true")])
    if case == "missing":
        rows = rows.drop(columns="Eligible")
    elif case == "date":
        rows["AsOf"] = "2025-02-01"
    elif case == "year":
        rows["Year"] = 2024
    elif case in {"empty_id", "blank_id"}:
        rows["PlayerID"] = "" if case == "empty_id" else " "
    elif case == "duplicate":
        rows = pd.concat([rows, rows])
    elif case in {"decision", "missing_decision"}:
        rows["Eligible"] = "maybe" if case == "decision" else ""
    if case != "unreadable":
        rows.to_csv(path, index=False)
    with pytest.raises(DataLoadError, match=message):
        read_eligibility(path, 2025, "2025-01-14")
