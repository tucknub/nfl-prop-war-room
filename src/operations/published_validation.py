from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.operations.current_role_pipeline import CANONICAL_KEY, REQUIRED_CANONICAL_COLUMNS, sha256


REQUIRED_SOURCE_NAMES = {"pbp", "player_stats", "rosters_weekly", "schedules", "snap_counts"}
ALLOWED_PARTIAL_STATUSES = {"clear", "suspected", "confirmed", "unreviewed"}


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return payload


def validate_published_role_outputs(
    season: int,
    output_dir: str | Path,
    *,
    require_published_status: bool = True,
) -> dict[str, Any]:
    root = Path(output_dir)
    files = {
        "canonical": root / f"canonical_role_{season}_live.csv.gz",
        "situational": root / f"situational_player_week_{season}_live.csv.gz",
        "production": root / f"game_player_usage_{season}_live.csv.gz",
        "events": root / f"opportunity_events_{season}_live.csv.gz",
        "partial": root / f"partial_game_status_{season}_live.csv.gz",
        "join": root / f"join_coverage_{season}_live.csv",
        "source": root / f"source_coverage_{season}_live.csv",
        "manifest": root / f"role_research_manifest_{season}.json",
        "validation": root / f"role_research_validation_{season}.json",
        "status": root / f"role_research_status_{season}.json",
        "source_input": root / f"source_input_manifest_{season}_live.csv",
        "completion": root / f"completion_gate_{season}.csv",
    }
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, observed: Any, expected: Any) -> None:
        checks.append(
            {
                "check": name,
                "passed": bool(passed),
                "observed": observed,
                "expected": expected,
            }
        )

    missing = sorted(name for name, path in files.items() if not path.exists())
    add("required_files_exist", not missing, missing, [])
    if missing:
        return {
            "schema_version": 1,
            "season": season,
            "status": "FAIL",
            "published_through_week": None,
            "checks": checks,
        }

    manifest = _read_json(files["manifest"])
    validation = _read_json(files["validation"])
    status = _read_json(files["status"])
    through_week = int(manifest.get("published_through_week") or 0)

    add("manifest_season", int(manifest.get("season") or 0) == season, manifest.get("season"), season)
    add("manifest_through_week", 1 <= through_week <= 18, through_week, "1..18")
    add("builder_validation_pass", validation.get("status") == "PASS", validation.get("status"), "PASS")
    expected_state = "PUBLISHED" if require_published_status else {"PUBLISHED", "VALIDATED_NOT_PUBLISHED"}
    status_ok = status.get("status") == expected_state if isinstance(expected_state, str) else status.get("status") in expected_state
    add("operational_status", status_ok, status.get("status"), expected_state)
    add(
        "status_week_matches_manifest",
        int(status.get("published_through_week") or 0) == through_week,
        status.get("published_through_week"),
        through_week,
    )

    hashes = manifest.get("output_hashes") or {}
    for key in ("canonical", "situational", "production", "events", "partial", "join", "source"):
        expected_hash = str(hashes.get(f"{key}_sha256") or "")
        observed_hash = sha256(files[key])
        add(f"{key}_hash", bool(expected_hash) and observed_hash == expected_hash, observed_hash, expected_hash)

    canonical = pd.read_csv(files["canonical"], compression="gzip", low_memory=False)
    situational = pd.read_csv(files["situational"], compression="gzip", low_memory=False)
    production = pd.read_csv(files["production"], compression="gzip", low_memory=False)
    events = pd.read_csv(files["events"], compression="gzip", low_memory=False)
    partial = pd.read_csv(files["partial"], compression="gzip", low_memory=False)
    source_coverage = pd.read_csv(files["source"], low_memory=False)
    source_input = pd.read_csv(files["source_input"], low_memory=False)
    completion = pd.read_csv(files["completion"], low_memory=False)

    add("canonical_not_empty", not canonical.empty, len(canonical), "> 0")
    add(
        "canonical_required_columns",
        set(REQUIRED_CANONICAL_COLUMNS).issubset(canonical.columns),
        sorted(set(REQUIRED_CANONICAL_COLUMNS).difference(canonical.columns)),
        [],
    )
    add("canonical_unique_key", not canonical.duplicated(CANONICAL_KEY).any(), int(canonical.duplicated(CANONICAL_KEY).sum()), 0)
    canonical_seasons = sorted(pd.to_numeric(canonical["season"], errors="coerce").dropna().astype(int).unique().tolist())
    canonical_weeks = sorted(pd.to_numeric(canonical["week"], errors="coerce").dropna().astype(int).unique().tolist())
    add("canonical_season", canonical_seasons == [season], canonical_seasons, [season])
    add("canonical_consecutive_weeks", canonical_weeks == list(range(1, through_week + 1)), canonical_weeks, list(range(1, through_week + 1)))
    add("canonical_quality_pass", canonical["data_quality_pass"].fillna(False).astype(bool).all(), int((~canonical["data_quality_pass"].fillna(False).astype(bool)).sum()), 0)
    add("participation_not_fabricated", canonical["participation_play_coverage"].isna().all(), int(canonical["participation_play_coverage"].notna().sum()), 0)

    completed_ids = sorted(str(value) for value in manifest.get("completed_game_ids") or [])
    canonical_ids = sorted(canonical["game_id"].astype(str).unique().tolist())
    add("completed_game_ids_match", canonical_ids == completed_ids, canonical_ids, completed_ids)

    add("situational_not_empty", not situational.empty, len(situational), "> 0")
    add("production_not_empty", not production.empty, len(production), "> 0")
    add("events_not_empty", not events.empty, len(events), "> 0")
    add(
        "event_unique_grain",
        not events.duplicated(["season", "week", "game_id", "play_id", "team", "player_id", "opportunity_type"]).any(),
        int(events.duplicated(["season", "week", "game_id", "play_id", "team", "player_id", "opportunity_type"]).sum()),
        0,
    )
    add(
        "production_unique_grain",
        not production.duplicated(["season", "week", "game_id", "team", "player_id"]).any(),
        int(production.duplicated(["season", "week", "game_id", "team", "player_id"]).sum()),
        0,
    )
    partial_values = set(partial["partial_game_status"].fillna("").astype(str).str.lower())
    add("partial_status_values", partial_values.issubset(ALLOWED_PARTIAL_STATUSES), sorted(partial_values), sorted(ALLOWED_PARTIAL_STATUSES))
    if "evidence_source" in partial:
        confirmed = partial["partial_game_status"].fillna("").astype(str).str.lower().eq("confirmed")
        confirmed_manual = partial.loc[confirmed, "evidence_source"].fillna("").astype(str).eq("manual_override").all()
        add("confirmed_partial_has_manual_evidence", confirmed_manual, int(confirmed.sum()), "all confirmed rows use manual_override")

    source_names = set(source_input["source"].astype(str))
    add("required_sources_present", REQUIRED_SOURCE_NAMES.issubset(source_names), sorted(source_names), sorted(REQUIRED_SOURCE_NAMES))
    required_rows = source_input[source_input["source"].isin(REQUIRED_SOURCE_NAMES)]
    source_errors = required_rows["error"].fillna("").astype(str).str.strip()
    add("required_sources_clean", source_errors.eq("").all(), required_rows.loc[source_errors.ne(""), ["source", "error"]].to_dict("records"), [])
    latest_weeks = pd.to_numeric(required_rows.loc[required_rows["source"].ne("schedules"), "latest_week"], errors="coerce")
    add("required_sources_reach_published_week", latest_weeks.dropna().ge(through_week).all(), latest_weeks.dropna().tolist(), f">= {through_week}")

    completion["week"] = pd.to_numeric(completion["week"], errors="coerce")
    admitted = completion[completion["week"].le(through_week)]
    add("completion_gate_all_pass", admitted["complete"].fillna(False).astype(bool).all(), int((~admitted["complete"].fillna(False).astype(bool)).sum()), 0)
    add("completion_gate_week_coverage", sorted(admitted["week"].dropna().astype(int).unique().tolist()) == list(range(1, through_week + 1)), sorted(admitted["week"].dropna().astype(int).unique().tolist()), list(range(1, through_week + 1)))

    if not source_coverage.empty:
        row = source_coverage.iloc[0]
        add("source_coverage_week", int(row.get("through_week") or 0) == through_week, row.get("through_week"), through_week)
        add("source_coverage_games", int(row.get("completed_games") or 0) == len(completed_ids), row.get("completed_games"), len(completed_ids))
        add("opportunity_identity_coverage", float(row.get("opportunity_identity_coverage") or 0) == 1.0, row.get("opportunity_identity_coverage"), 1.0)
        add("snap_identity_coverage", float(row.get("snap_identity_coverage") or 0) >= 0.99, row.get("snap_identity_coverage"), ">= 0.99")
        add("opportunity_to_snap_coverage", float(row.get("opportunity_to_snap_coverage") or 0) >= 0.995, row.get("opportunity_to_snap_coverage"), ">= 0.995")

    return {
        "schema_version": 1,
        "season": season,
        "status": "PASS" if all(check["passed"] for check in checks) else "FAIL",
        "published_through_week": through_week,
        "checks": checks,
    }
