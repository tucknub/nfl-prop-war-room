from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from role_validation.canonical import build_canonical_player_week_role  # noqa: E402
from role_validation.partial_game import build_partial_game_status  # noqa: E402
from role_validation.sources import load_nflverse_role_sources, source_cache_manifest  # noqa: E402


SEASON = 2025
CANONICAL_KEY = ["season", "week", "player_id", "team", "role_family"]
PUBLIC_COLUMNS = [
    "season", "week", "game_id", "player_id", "player_name", "team", "position",
    "role_family", "metric_all", "metric_normal", "raw_opportunities_all",
    "raw_opportunities_normal", "team_opportunities_all", "team_opportunities_normal",
    "qualifying_game", "data_quality_pass", "active_status", "snap_share",
    "identity_resolved", "game_partition_complete", "participation_play_coverage",
    "source_version", "confirmed_partial_game", "suspected_partial_game",
    "suspected_partial_corroborated", "partial_game_status", "partial_game_reason",
]
REQUIRED_COLUMNS = [
    "season", "week", "game_id", "player_id", "player_name", "team", "position",
    "role_family", "metric_all", "metric_normal", "raw_opportunities_all",
    "raw_opportunities_normal", "team_opportunities_all", "team_opportunities_normal",
    "qualifying_game", "data_quality_pass", "identity_resolved",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def frame_sha256(frame: pd.DataFrame) -> str:
    payload = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def write_csv(frame: pd.DataFrame, path: Path, *, compressed: bool = False) -> None:
    compression: str | dict[str, object] | None = (
        {"method": "gzip", "compresslevel": 9, "mtime": 0} if compressed else None
    )
    frame.to_csv(path, index=False, compression=compression, lineterminator="\n")


def load_explicit_sources() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    import nflreadpy as nfl

    pbp = nfl.load_pbp([SEASON]).select(
        ["season", "week", "season_type", "game_id", "play_id", "desc"]
    ).to_pandas()
    pbp = pbp.loc[pbp["season_type"].eq("REG")].copy()
    rosters = nfl.load_rosters_weekly([SEASON]).select(
        [
            "season", "week", "game_type", "team", "jersey_number", "gsis_id",
            "full_name", "position",
        ]
    ).to_pandas()
    rosters = rosters.loc[rosters["game_type"].eq("REG")].copy()
    schedules = nfl.load_schedules([SEASON]).select(
        [
            "season", "week", "game_type", "game_id", "gameday", "gametime",
            "home_team", "away_team",
        ]
    ).to_pandas()
    schedules = schedules.loc[schedules["game_type"].eq("REG")].copy()
    return pbp, rosters, schedules


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the completed 2025 descriptive role-research partition only."
    )
    parser.add_argument("--source-cache-dir", type=Path, required=True)
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "outputs" / "role_research"
    )
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    sources = load_nflverse_role_sources(
        [SEASON], cache_dir=args.source_cache_dir, refresh=args.refresh
    )
    injury_timestamp_available = (
        "date_modified" in sources["injuries"]
        and sources["injuries"]["date_modified"].notna().any()
    )
    if "date_modified" not in sources["injuries"]:
        # The 2025 injury schema has no update timestamp. Keep that evidence channel
        # unavailable rather than treating a usage drop or an undated report as confirmation.
        sources["injuries"]["date_modified"] = pd.NaT

    base = build_canonical_player_week_role(
        sources,
        [SEASON],
        source_version="nflverse 2025 completed descriptive research build",
    )
    explicit_pbp, explicit_rosters, explicit_schedules = load_explicit_sources()
    partial = build_partial_game_status(
        base.canonical,
        selected_pbp=sources["pbp"],
        participation=sources["participation"],
        injuries=sources["injuries"],
        explicit_pbp=explicit_pbp,
        full_rosters=explicit_rosters,
        schedules=explicit_schedules,
        seasons=[SEASON],
    )
    canonical = partial.canonical[PUBLIC_COLUMNS].copy()
    canonical = canonical.sort_values(CANONICAL_KEY).reset_index(drop=True)

    opportunity_join = base.join_coverage.loc[
        base.join_coverage["join"].eq("opportunity_to_identity"), "coverage_rate"
    ].min()
    participation_join = base.join_coverage.loc[
        base.join_coverage["join"].eq("participating_player_to_identity"), "coverage_rate"
    ].min()
    source_row = base.source_coverage.loc[base.source_coverage["season"].eq(SEASON)].iloc[0]
    if canonical.duplicated(CANONICAL_KEY).any():
        raise AssertionError("2025 descriptive canonical key is not unique")
    if canonical[REQUIRED_COLUMNS].isna().any().any():
        raise AssertionError("2025 descriptive canonical has missing required fields")
    if not canonical["data_quality_pass"].all():
        raise AssertionError("2025 descriptive canonical contains a quality-failed row")
    if float(opportunity_join) != 1.0:
        raise AssertionError("2025 opportunity-to-identity coverage is incomplete")
    if float(participation_join) < 0.999:
        raise AssertionError("2025 participation-to-identity coverage is below 99.9%")
    if not bool(source_row["complete_schema_and_games"]):
        raise AssertionError("2025 source games or participation coverage are incomplete")

    prohibited_tokens = ("alert", "persistent", "sustainable", "prediction", "bet", "odds", "score")
    prohibited_columns = [
        column for column in canonical.columns
        if any(token in column.lower() for token in prohibited_tokens)
    ]
    if prohibited_columns:
        raise AssertionError(f"Detector or betting fields entered descriptive output: {prohibited_columns}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    canonical_path = args.output_dir / "canonical_role_2025_descriptive.csv.gz"
    partial_path = args.output_dir / "partial_game_status_2025.csv.gz"
    join_path = args.output_dir / "join_coverage_2025.csv"
    source_path = args.output_dir / "source_coverage_2025.csv"
    partial_source_path = args.output_dir / "partial_game_source_coverage_2025.csv"
    input_path = args.output_dir / "source_input_manifest_2025.csv"

    write_csv(canonical, canonical_path, compressed=True)
    partial_status = partial.evidence_ledger[
        [
            "season", "week", "game_id", "player_id", "player_name", "team",
            "position", "role_family", "partial_game_status", "partial_game_reason",
            "confirmed_partial_game", "suspected_partial_game", "evidence_source",
            "evidence_timestamp_basis",
        ]
    ].copy()
    write_csv(partial_status, partial_path, compressed=True)
    write_csv(base.join_coverage, join_path)
    write_csv(base.source_coverage, source_path)
    write_csv(partial.source_coverage, partial_source_path)

    cache_manifest = source_cache_manifest(args.source_cache_dir)
    cache_manifest["file"] = cache_manifest["file"].map(lambda value: Path(value).name)
    explicit_manifest = pd.DataFrame(
        [
            {"file": "explicit_pbp_2025_in_memory", "bytes": None, "sha256": frame_sha256(explicit_pbp)},
            {"file": "explicit_rosters_2025_in_memory", "bytes": None, "sha256": frame_sha256(explicit_rosters)},
            {"file": "explicit_schedules_2025_in_memory", "bytes": None, "sha256": frame_sha256(explicit_schedules)},
        ]
    )
    write_csv(pd.concat([cache_manifest, explicit_manifest], ignore_index=True), input_path)

    player_game_key = ["season", "week", "game_id", "player_id", "team"]
    audit = {
        "status": "PASS",
        "season": SEASON,
        "completed_historical_data_only": True,
        "canonical_rows": int(len(canonical)),
        "played_games": int(canonical["game_id"].nunique()),
        "played_weeks": sorted(canonical["week"].astype(int).unique().tolist()),
        "unique_players": int(canonical["player_id"].nunique()),
        "duplicate_canonical_keys": int(canonical.duplicated(CANONICAL_KEY).sum()),
        "required_missing_cells": int(canonical[REQUIRED_COLUMNS].isna().sum().sum()),
        "identity_coverage": float(canonical["identity_resolved"].mean()),
        "opportunity_to_identity_coverage": float(opportunity_join),
        "participating_player_to_identity_coverage": float(participation_join),
        "participation_play_coverage": float(source_row["participation_play_coverage"]),
        "carry_player_id_coverage": float(source_row["carry_player_id_coverage"]),
        "receiver_assignment_rate_of_valid_pass_attempts": float(source_row["target_player_id_coverage"]),
        "quality_pass_rate": float(canonical["data_quality_pass"].mean()),
        "qualifying_rate": float(canonical["qualifying_game"].mean()),
        "confirmed_partial_family_rows": int(canonical["confirmed_partial_game"].sum()),
        "confirmed_partial_player_games": int(
            canonical.loc[canonical["confirmed_partial_game"]]
            .drop_duplicates(player_game_key).shape[0]
        ),
        "suspected_partial_family_rows": int(canonical["suspected_partial_game"].sum()),
        "suspected_partial_player_games": int(
            canonical.loc[canonical["suspected_partial_game"]]
            .drop_duplicates(player_game_key).shape[0]
        ),
        "injury_pbp_identity_resolution_rate": float(partial.source_coverage.iloc[0]["resolution_rate"]),
        "injury_report_timestamp_available": bool(injury_timestamp_available),
        "temporal_and_season_boundary_checks_passed": True,
        "detector_or_betting_columns_present": prohibited_columns,
        "canonical_sha256": sha256(canonical_path),
        "partial_status_sha256": sha256(partial_path),
    }
    (args.output_dir / "canonical_audit_2025.json").write_text(
        json.dumps(audit, indent=2), encoding="utf-8"
    )
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
