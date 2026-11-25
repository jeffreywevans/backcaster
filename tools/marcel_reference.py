"""Clean user-supplied Marcel forecasts and compare them with a Backcaster build."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import numpy as np
import pandas as pd

from backcaster.cli import _default_data_dir
from backcaster.data import DataLoadError
from backcaster.lahman import LahmanSource
from backcaster.marcel import ProjectionError
from backcaster.outputs import _batting_export_values, _display_frame, _format_number
from backcaster.stat_columns import BATTING_STAT_COLUMNS, PITCHING_STAT_COLUMNS

DEFAULT_REFERENCE_DIR = Path(__file__).resolve().parents[1] / "references" / "marcel" / "data"
KINDS = {"batter": "batting", "pitcher": "pitching"}
STATS = {"batting": BATTING_STAT_COLUMNS, "pitching": PITCHING_STAT_COLUMNS}
EXTRA_STATS = {"batting": ("wOBA",), "pitching": ("BaseRunsER", "G", "GS", "Replacement")}
KEY_STATS = {"batting": "OPS", "pitching": "ERA"}
ARCHIVE_NAME = re.compile(r"(\d{4}) projections (batter|pitcher)\.csv")
NAME_ALIASES = {
    "jacoblatz": "jakelatz",
    "joshuapalacios": "joshpalacios",
    "louisvarland": "louievarland",
    "mattbowman": "matthewbowman",
    "matthewboyd": "mattboyd",
    "michaelking": "mikeking",
    "michaelsoroka": "mikesoroka",
}


def read_source_csv(data: bytes) -> pd.DataFrame:
    try:
        return pd.read_csv(BytesIO(data), encoding="utf-8-sig")
    except UnicodeDecodeError:
        return pd.read_csv(BytesIO(data), encoding="cp1252")


def parse_innings(values: pd.Series) -> pd.Series:
    """Read baseball notation as true decimal innings for arithmetic."""
    parsed = values.astype("string").str.strip().str.extract(r"^(\d+)(?:\.([012])0*)?$")
    if (values.notna() & parsed[0].isna()).any():
        raise ValueError("Expected baseball innings with zero, one, or two extra outs.")
    return pd.to_numeric(parsed[0]) + pd.to_numeric(parsed[1].fillna("0")) / 3


def clean_table(data: bytes, year: int, kind: str) -> tuple[pd.DataFrame, dict[str, int]]:
    source = read_source_csv(data)
    source.columns = source.columns.str.strip()
    source_rows = len(source)
    table = source.dropna(how="all").copy()
    blank_rows = source_rows - len(table)
    table = table.drop_duplicates().copy()
    duplicate_rows = source_rows - blank_rows - len(table)
    historical = "playerID" in table
    if historical and not table["year"].eq(year).all():
        raise ValueError("Archive filename and projection year disagree.")
    if historical:
        table["Name"] = table["nameFirst"].fillna("") + " " + table["nameLast"].fillna("")
        table = table.rename(columns={f"m{stat}": stat for stat in (*STATS[kind], "G", "GS")})
    table = table.rename(
        columns={
            "playerID": "PlayerID",
            "mGIDP": "GDP",
            "lgID": "League",
            "bsrER": "BaseRunsER",
            "mRepl": "Replacement",
            "Rel": "Reliability",
            "reliability": "Reliability",
        }
    )
    table["Name"] = table["Name"].astype("string").str.strip()
    table["Year"] = year
    reliability = table["Reliability"].astype("string").str.strip().replace("-", pd.NA)
    numeric_rel = pd.to_numeric(reliability.str.rstrip("%")).astype(float)
    table["Reliability"] = numeric_rel.mask(
        reliability.str.endswith("%", na=False) | numeric_rel.gt(1), numeric_rel / 100
    )
    if not table["Reliability"].dropna().between(0, 1).all():
        raise ValueError("Reliability must be a fraction or percentage.")
    if kind == "batting" and historical:
        table[["TB", "BA", "OBP", "SLG", "OPS"]] = 0.0
        derived = _batting_export_values(table)
        for stat in ("TB", "BA", "OBP", "SLG", "OPS"):
            table[stat] = derived[stat].map(lambda n: _format_number(n, 0 if stat == "TB" else 3))
    if kind == "pitching":
        parse_innings(table["IP"])
    axes = ["PlayerID"] if historical else ["Name", "Age"]
    if table[axes].isna().any().any() or table["Name"].eq("").any() or table.duplicated(axes).any():
        raise ValueError(f"Missing or conflicting player identity in {year} {kind}.")
    columns = (
        "Year",
        "PlayerID",
        "Name",
        "Age",
        "League",
        "Reliability",
        *STATS[kind],
        *EXTRA_STATS[kind],
    )
    table = table[[k for k in columns if k in table]]
    required = {"Year", "Name", "Age", "Reliability", KEY_STATS[kind]}
    if not required <= set(table):
        raise ValueError(f"Missing reference fields: {', '.join(sorted(required - set(table)))}.")
    return table, {"rows": len(table), "blank_rows": blank_rows, "duplicate_rows": duplicate_rows}


def clean_archive(archive_path: Path, reference_dir: Path) -> dict[str, object]:
    """Validate the entire ZIP before writing canonical CSVs and their manifest."""
    files = {}
    manifest: dict[str, object] = {
        "source_sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest()
    }
    with ZipFile(archive_path) as archive:
        for member in sorted(archive.infolist(), key=lambda entry: entry.filename):
            if member.is_dir():
                continue
            name = Path(member.filename).name
            match = ARCHIVE_NAME.fullmatch(name)
            if match is None:
                raise ValueError(f"Unexpected forecast filename: {member.filename}")
            year, kind = int(match[1]), KINDS[match[2]]
            filename = f"{year}-{kind}.csv"
            if filename in files:
                raise ValueError(f"Multiple sources for {filename}.")
            source = archive.read(member)
            table, counts = clean_table(source, year, kind)
            output = table.to_csv(index=False, lineterminator="\n").encode("utf-8")
            files[filename] = (
                output,
                {
                    "file": filename,
                    "source": name,
                    **counts,
                    "source_sha256": hashlib.sha256(source).hexdigest(),
                    "sha256": hashlib.sha256(output).hexdigest(),
                },
            )
    if not files:
        raise ValueError("The archive contains no forecast CSVs.")
    reference_dir.mkdir(parents=True, exist_ok=True)
    for filename, (data, _) in files.items():
        (reference_dir / filename).write_bytes(data)
    manifest["files"] = [record for _, record in files.values()]
    (reference_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def name_key(name: str) -> str:
    letters = unicodedata.normalize("NFKD", name.casefold())
    ascii_name = "".join(char for char in letters if not unicodedata.combining(char))
    parts = re.findall(r"[a-z0-9]+", ascii_name)
    if parts and parts[-1] in {"jr", "sr", "ii", "iii", "iv"}:
        parts.pop()
    if len(parts) > 2 and len(parts[0]) > 1:
        parts = [parts[0], *(part for part in parts[1:-1] if len(part) > 1), parts[-1]]
    key = "".join(parts)
    return NAME_ALIASES.get(key, key)


def match_reference(reference: pd.DataFrame, projected: pd.DataFrame) -> pd.DataFrame:
    """Keep source IDs and match name-only rows against the current projection."""
    if "PlayerID" in reference:
        return reference
    reference = reference.copy()
    candidates = projected.assign(NameKey=projected["Name"].map(name_key)).groupby("NameKey")
    player_ids = []
    for name, age in reference[["Name", "Age"]].itertuples(index=False, name=None):
        key = name_key(name)
        if key not in candidates.groups:
            player_ids.append(pd.NA)
            continue
        options = candidates.get_group(key)
        if len(options) > 1:
            options = options[options["Age"].eq(age)]
        player_ids.append(options["PlayerID"].iloc[0] if len(options) == 1 else pd.NA)
    reference["PlayerID"] = player_ids
    return reference


def score_comparison(
    projected: pd.DataFrame, reference: pd.DataFrame, kind: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compare displayed values and calculate Backcaster-minus-reference errors."""
    shown = _display_frame(projected).set_index("PlayerID")
    expected = reference.set_index("PlayerID")
    comparable = ["Age", "Reliability", *STATS[kind]]
    stats = [col for col in comparable if col in shown.columns and col in expected.columns]
    if not stats:
        raise ValueError("No shared reference statistics.")
    build = shown[["Name", *stats]].copy()
    paired = expected[stats].copy()
    for stat in stats:
        if stat == "IP":
            build[stat] = parse_innings(build[stat]).astype(float)
            paired[stat] = parse_innings(paired[stat]).astype(float)
            if paired[stat].notna().any() and paired[stat].dropna().mod(1).eq(0).all():
                build["IP (whole)"] = np.floor(build[stat] + 0.5)
                paired["IP (whole)"] = paired[stat]
        else:
            build[stat] = pd.to_numeric(build[stat], errors="coerce")
            paired[stat] = pd.to_numeric(paired[stat])
            if stat == "Reliability":
                build[stat] = build[stat].round(2)
    errors = build.drop(columns="Name").sub(paired)
    numeric = pd.DataFrame(
        {
            "matched": errors.count(),
            "exact": errors.eq(0).sum(),
            "MAE": errors.abs().mean(),
            "bias": errors.mean(),
            "max_abs": errors.abs().max(),
        }
    )
    return numeric, pd.concat({"Backcaster": build, "Marcel": paired, "Delta": errors}, axis=1)


def load_reference(reference_dir: Path, year: int, kind: str) -> pd.DataFrame:
    filename = f"{year}-{kind}.csv"
    manifest_path = reference_dir / "manifest.json"
    data_path = reference_dir / filename
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        hashes = {entry["file"]: entry["sha256"] for entry in manifest["files"]}
        if filename not in hashes:
            raise ValueError(f"No {year} {kind} forecast in the reference manifest.")
        data = data_path.read_bytes()
        if hashlib.sha256(data).hexdigest() != hashes[filename]:
            raise ValueError(
                f"Reference checksum mismatch for {filename}. Run clean again or restore the reference file."
            )
    else:
        data = data_path.read_bytes()
    reference = pd.read_csv(BytesIO(data), encoding="utf-8", dtype={"PlayerID": str})
    if not reference["Year"].eq(year).all():
        raise ValueError("Reference file contains a different projection year.")
    return reference


def compare(reference_dir: Path, data_dir: str, year: int, kind: str, player_id: str | None) -> str:
    reference = load_reference(reference_dir, year, kind)
    projected = LahmanSource(data_dir).project("batch", year, kind)
    mapped = match_reference(reference, projected)
    if mapped["PlayerID"].dropna().duplicated().any():
        raise ValueError("Multiple reference rows map to the same Lahman PlayerID.")
    present = mapped["PlayerID"].isin(projected["PlayerID"])
    matched = mapped[present]
    build_only = projected[~projected["PlayerID"].isin(matched["PlayerID"])]
    lines = [
        f"{year} {kind} | {len(matched)} matched | {len(reference) - len(matched)} reference only"
        f" | {len(build_only)} Backcaster only"
    ]
    if not present.all():
        missing = mapped.loc[~present, "Name"].astype(str).tolist()
        suffix = " …" if len(missing) > 10 else ""
        lines.append(f"Reference-only players: {', '.join(missing[:10])}{suffix}")
    if player_id is not None:
        matched = matched[matched["PlayerID"].eq(player_id)]
        if matched.empty:
            raise ValueError(
                f"PlayerID {player_id} has no matched reference forecast for {year} {kind}."
            )
    if matched.empty:
        raise ValueError(f"No players match the {year} {kind} reference.")
    selected = projected[projected["PlayerID"].isin(matched["PlayerID"])]
    scores, detail = score_comparison(selected, matched, kind)
    if player_id is not None:
        row = detail.loc[player_id]
        side_by_side = row.unstack(level=0).drop(index="Name").astype(float)
        lines.append(f"\n{row['Backcaster', 'Name']} ({player_id})")
        lines.append(side_by_side.to_string(float_format=lambda value: f"{value:.3f}"))
    else:
        lines.append(
            scores.dropna(subset="MAE").to_string(float_format=lambda value: f"{value:.4f}")
        )
        stat = KEY_STATS[kind]
        if ("Delta", stat) in detail:
            worst_ids = detail["Delta", stat].abs().nlargest(5).index
            columns = [
                ("Backcaster", "Name"),
                ("Backcaster", stat),
                ("Marcel", stat),
                ("Delta", stat),
            ]
            worst = detail.loc[worst_ids, columns].copy()
            worst.columns = ["Name", "Backcaster", "Marcel", "Delta"]
            lines.append(
                f"\nLargest {stat} differences\n{worst.to_string(float_format=lambda value: f'{value:.3f}')}"
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    cleaner = commands.add_parser("clean", help="Normalize a Marcel ZIP and record its provenance")
    cleaner.add_argument("archive", type=Path)
    checker = commands.add_parser(
        "compare", help="Compare a season with the installed Backcaster build"
    )
    checker.add_argument("--year", type=int, required=True)
    checker.add_argument("--kind", choices=tuple(STATS), required=True)
    checker.add_argument("--data-dir", default=_default_data_dir())
    checker.add_argument("--player-id", help="Show the full comparison for one Lahman PlayerID")
    for command in (cleaner, checker):
        command.add_argument("--reference-dir", type=Path, default=DEFAULT_REFERENCE_DIR)
    args = parser.parse_args(argv)
    try:
        if args.command == "clean":
            manifest = clean_archive(args.archive, args.reference_dir)
            print(f"Cleaned {len(manifest['files'])} forecast files in {args.reference_dir}")
        else:
            print(compare(args.reference_dir, args.data_dir, args.year, args.kind, args.player_id))
    except (BadZipFile, DataLoadError, KeyError, OSError, ProjectionError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
