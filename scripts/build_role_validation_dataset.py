from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from role_validation.audit import audit_player_week_table
from role_validation.canonical import build_canonical_player_week_role
from role_validation.config import load_config
from role_validation.sources import load_nflverse_role_sources, source_cache_manifest


def parse_seasons(text: str) -> list[int]:
    start, end = [int(value) for value in text.split("-")]
    return list(range(start, end + 1))


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def missingness(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for season, group in frame.groupby("season"):
        for column in frame.columns:
            rows.append(
                {
                    "season": season,
                    "column": column,
                    "null_rows": int(group[column].isna().sum()),
                    "null_rate": float(group[column].isna().mean()),
                }
            )
    return pd.DataFrame(rows)


def reconciliation(canonical: pd.DataFrame, stats: pd.DataFrame) -> pd.DataFrame:
    canonical_seasons = set(pd.to_numeric(canonical["season"], errors="coerce").dropna().astype(int))
    stats = stats.loc[
        stats["season_type"].fillna("").astype(str).str.upper().eq("REG")
        & stats["position"].fillna("").astype(str).str.upper().isin(["RB", "WR", "TE"])
        & pd.to_numeric(stats["season"], errors="coerce").isin(canonical_seasons)
    ].copy()
    stats["position"] = stats["position"].astype(str).str.upper()
    source = (
        stats.groupby(["season", "week", "player_id", "team", "position"], as_index=False)
        .agg(source_carries=("carries", "sum"), source_targets=("targets", "sum"))
    )
    rb = canonical.loc[canonical["role_family"].eq("rb_carry_share"), [
        "season", "week", "player_id", "team", "position", "raw_opportunities_all"
    ]].rename(columns={"raw_opportunities_all": "canonical_carries"})
    targets = canonical.loc[
        canonical["role_family"].isin(["wr_target_share", "te_target_share"]),
        ["season", "week", "player_id", "team", "position", "raw_opportunities_all"],
    ].rename(columns={"raw_opportunities_all": "canonical_targets"})
    check = source.merge(rb, on=["season", "week", "player_id", "team", "position"], how="left")
    check = check.merge(targets, on=["season", "week", "player_id", "team", "position"], how="left")
    check["canonical_carries"] = check["canonical_carries"].fillna(0)
    check["canonical_targets"] = check["canonical_targets"].fillna(0)
    check["carry_difference"] = check["canonical_carries"] - check["source_carries"]
    check["target_difference"] = check["canonical_targets"] - check["source_targets"]
    rows = []
    for season, group in check.groupby("season"):
        rb_group = group.loc[group["position"].eq("RB")]
        receiver_group = group.loc[group["position"].isin(["WR", "TE"])]
        rows.extend(
            [
                {
                    "season": season, "metric": "RB carries", "source_total": rb_group["source_carries"].sum(),
                    "canonical_total": rb_group["canonical_carries"].sum(),
                    "absolute_difference": rb_group["carry_difference"].abs().sum(),
                    "exact_row_match_rate": float(rb_group["carry_difference"].eq(0).mean()) if len(rb_group) else float("nan"),
                },
                {
                    "season": season, "metric": "WR/TE targets", "source_total": receiver_group["source_targets"].sum(),
                    "canonical_total": receiver_group["canonical_targets"].sum(),
                    "absolute_difference": receiver_group["target_difference"].abs().sum(),
                    "exact_row_match_rate": float(receiver_group["target_difference"].eq(0).mean()) if len(receiver_group) else float("nan"),
                },
            ]
        )
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the canonical PropWar player-week-role table.")
    parser.add_argument("--seasons", default="2018-2025")
    parser.add_argument("--coverage-seasons", default="2017-2025")
    parser.add_argument("--cache-dir", default="data/raw/role_validation")
    parser.add_argument("--output-dir", default="outputs/role_validation")
    parser.add_argument("--config", default="config/role_change_validation.yaml")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    seasons = parse_seasons(args.seasons)
    coverage_seasons = parse_seasons(args.coverage_seasons)
    output_dir = ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    config = load_config(ROOT / args.config)
    sources = load_nflverse_role_sources(
        coverage_seasons, cache_dir=ROOT / args.cache_dir, refresh=args.refresh
    )
    result = build_canonical_player_week_role(
        sources,
        seasons=seasons,
        q3_threshold=int(config["normal_game"]["q3_garbage_abs_score_diff"]),
        q4_threshold=int(config["normal_game"]["q4_garbage_abs_score_diff"]),
        source_version="nflverse/nflreadpy 0.1.5; cached selected columns",
    )
    canonical_path = output_dir / "canonical_player_week_role.csv.gz"
    result.canonical.to_csv(
        canonical_path,
        index=False,
        compression={"method": "gzip", "compresslevel": 9, "mtime": 0},
    )
    result.exclusions.to_csv(output_dir / "exclusion_ledger.csv", index=False)
    result.join_coverage.to_csv(output_dir / "join_coverage.csv", index=False)
    result.source_coverage.to_csv(output_dir / "source_coverage_by_season.csv", index=False)
    result.context_sensitivity.to_csv(output_dir / "normal_game_sensitivity_2018_2020.csv", index=False)
    missingness(result.canonical).to_csv(output_dir / "canonical_missingness_by_season.csv", index=False)
    reconciliation(result.canonical, sources["player_stats"]).to_csv(
        output_dir / "opportunity_reconciliation.csv", index=False
    )

    audit_window = result.canonical.loc[result.canonical["season"].between(2018, 2020)]
    audit = audit_player_week_table(
        audit_window,
        required_columns=config["data"]["required_columns"],
        key_columns=config["data"]["key_columns"],
        share_columns=config["data"]["share_columns"],
    )
    audit.summary.to_csv(output_dir / "data_audit_summary_2018_2020.csv", index=False)
    audit.issues.to_csv(output_dir / "data_audit_issues_2018_2020.csv", index=False)
    family_counts = (
        audit_window.groupby(["season", "role_family"])
        .agg(
            rows=("player_id", "size"),
            players=("player_id", "nunique"),
            qualifying_rows=("qualifying_game", "sum"),
            data_quality_pass_rows=("data_quality_pass", "sum"),
        )
        .reset_index()
    )
    family_counts.to_csv(output_dir / "canonical_row_counts_2018_2020.csv", index=False)
    duplicates = audit_window.loc[
        audit_window.duplicated(config["data"]["key_columns"], keep=False)
    ]
    duplicates.to_csv(output_dir / "canonical_duplicate_keys_2018_2020.csv", index=False)
    limitations = pd.DataFrame(
        [
            {
                "severity": "high",
                "limitation": "partial_game_exclusions",
                "status": "UNRELIABLE_SOURCE",
                "detail": "No trustworthy in-game player-exit flag exists in PBP, participation, snaps, rosters, or injury reports. partial_game_flag is present but conservatively false and is not release-grade.",
                "leakage_risk": "Using next-week injury reports or outcome-correlated snap drops would introduce look-ahead or selection bias.",
            },
            {
                "severity": "medium",
                "limitation": "late_backup_only",
                "status": "UNAVAILABLE",
                "detail": "No trustworthy late-backup-only source field exists; the protocol permits exclusion only when reliably identified.",
                "leakage_risk": "No future data used; flag remains false and explicitly unreliable.",
            },
        ]
    )
    limitations.to_csv(output_dir / "validation_limitations.csv", index=False)
    cache_manifest = source_cache_manifest(ROOT / args.cache_dir)
    cache_manifest.to_csv(output_dir / "source_cache_manifest.csv", index=False)
    run_manifest = {
        "seasons": seasons,
        "coverage_seasons": coverage_seasons,
        "canonical_rows": len(result.canonical),
        "audit_rows_2018_2020": len(audit_window),
        "audit_passed": bool(audit.passed),
        "canonical_path": str(canonical_path.relative_to(ROOT)),
        "canonical_sha256": file_sha256(canonical_path),
        "protocol_sha256": file_sha256(ROOT / "ROLE_CHANGE_VALIDATION_PROTOCOL.md"),
        "locked_decisions_sha256": file_sha256(ROOT / "LOCKED_DECISIONS.md"),
    }
    (output_dir / "canonical_build_manifest.json").write_text(
        json.dumps(run_manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps(run_manifest, indent=2))
    return 0 if audit.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
