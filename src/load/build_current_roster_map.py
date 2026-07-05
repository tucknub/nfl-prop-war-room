from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from src.common import output_path, project_path
from src.load.build_identity_crosswalk import canonical_team, normalize_player_name


MAP_COLUMNS = [
    "player_id", "player_name", "position", "historical_team", "current_team",
    "projection_team", "roster_status", "depth_chart_role", "source",
    "updated_at", "manual_override", "team_mapping_status", "validation_status", "notes",
]


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "approved"}


def _present(value: object) -> bool:
    return pd.notna(value) and str(value).strip() != ""


def _read_many(paths: Iterable[Path]) -> pd.DataFrame:
    frames = []
    for path in paths:
        try:
            frame = pd.read_csv(path, low_memory=False)
        except pd.errors.EmptyDataError:
            continue
        if not frame.empty:
            frame["_input_file"] = str(path)
            frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def discover_real_inputs(roster_dir: Path) -> tuple[list[Path], list[Path]]:
    files = list(roster_dir.glob("*.csv")) if roster_dir.exists() else []
    real = [p for p in files if "template" not in p.name.lower()]
    overrides = [p for p in real if "override" in p.name.lower()]
    rosters = [p for p in real if "override" not in p.name.lower()]
    return sorted(rosters), sorted(overrides)


def _identity_candidates(identity: pd.DataFrame, player_id: str, normalized_name: str) -> pd.DataFrame:
    if identity.empty:
        return identity
    if player_id:
        exact = identity[identity["player_id"].fillna("").astype(str).str.strip().eq(player_id)]
        if not exact.empty:
            return exact
    return identity[identity["normalized_player_name"].fillna("").astype(str).eq(normalized_name)]


def _latest_identity(candidates: pd.DataFrame) -> pd.Series | None:
    if candidates.empty:
        return None
    ranked = candidates.copy()
    ranked["_season"] = pd.to_numeric(ranked.get("season_max"), errors="coerce").fillna(-1)
    return ranked.sort_values(["_season", "team"], ascending=[False, True]).iloc[0]


def build_map_from_frames(rosters: pd.DataFrame, overrides: pd.DataFrame, identity: pd.DataFrame) -> pd.DataFrame:
    if rosters.empty:
        return pd.DataFrame(columns=MAP_COLUMNS)
    roster = rosters.copy()
    for col in ["player_id", "player_name", "position", "current_team", "roster_status", "depth_chart_role", "source", "source_url", "updated_at", "manual_override", "notes"]:
        if col not in roster.columns:
            roster[col] = ""
    roster["player_id"] = roster["player_id"].fillna("").astype(str).str.strip()
    roster["player_name"] = roster["player_name"].fillna("").astype(str).str.strip()
    roster["normalized_player_name"] = roster["player_name"].map(normalize_player_name)
    roster["current_team"] = roster["current_team"].map(canonical_team)

    override_lookup: dict[str, pd.Series] = {}
    if not overrides.empty:
        work = overrides.copy()
        for col in ["player_id", "player_name", "old_team", "override_current_team", "source", "source_url", "approved", "notes"]:
            if col not in work.columns:
                work[col] = ""
        work["player_id"] = work["player_id"].fillna("").astype(str).str.strip()
        work["normalized_player_name"] = work["player_name"].map(normalize_player_name)
        for _, override in work.iterrows():
            key = override["player_id"] or f"name:{override['normalized_player_name']}"
            override_lookup[key] = override

    rows = []
    for _, item in roster.iterrows():
        player_id = item["player_id"]
        normalized_name = item["normalized_player_name"]
        candidates = _identity_candidates(identity, player_id, normalized_name)
        id_exact = bool(player_id and not candidates.empty and candidates["player_id"].fillna("").astype(str).str.strip().eq(player_id).any())
        unique_ids = set(candidates["player_id"].fillna("").astype(str).str.strip()) - {""} if not candidates.empty else set()
        identity_row = _latest_identity(candidates)
        historical_team = canonical_team(identity_row.get("team", "")) if identity_row is not None else ""
        current_team = item["current_team"]
        key = player_id or f"name:{normalized_name}"
        override = override_lookup.get(key)
        override_applied = bool(override is not None and _truthy(override.get("approved", False)))
        if override_applied:
            current_team = canonical_team(override.get("override_current_team", current_team))
        changed_team = bool(historical_team and current_team and historical_team != current_team)
        source_confirmed = _present(item.get("source", "")) and _present(item.get("source_url", ""))

        reasons = []
        if candidates.empty:
            status = "BLOCKED"
            validation = "UNMATCHED_PLAYER"
            reasons.append("Current roster row cannot be matched to the identity crosswalk.")
        elif not player_id:
            status = "NEEDS REVIEW"
            validation = "MISSING_PLAYER_ID"
            reasons.append("Missing player_id; name-only matches require review.")
        elif not id_exact or len(unique_ids) > 1:
            status = "BLOCKED"
            validation = "IDENTITY_CONFLICT"
            reasons.append("Identity match is ambiguous or conflicts with player_id.")
        elif not current_team:
            status = "NEEDS DATA"
            validation = "MISSING_CURRENT_TEAM"
            reasons.append("Verified current_team is required.")
        elif changed_team and not (source_confirmed or override_applied):
            status = "NEEDS REVIEW"
            validation = "TEAM_CHANGE_UNVERIFIED"
            reasons.append(f"Team changed from {historical_team} to {current_team} without source URL or approved override.")
        elif _truthy(item.get("manual_override", False)) and not override_applied:
            status = "NEEDS REVIEW"
            validation = "OVERRIDE_NOT_APPROVED"
            reasons.append("Manual override is present but no approved override row was found.")
        else:
            status = "READY"
            validation = "PASS"
            reasons.append("Current team verified by identity match and source-backed roster data." if not override_applied else "Approved team override applied.")

        if changed_team:
            reasons.append(f"TEAM_CHANGE: {historical_team} -> {current_team}.")
        rows.append({
            "player_id": player_id,
            "player_name": item["player_name"],
            "position": str(item.get("position", "") or (identity_row.get("position", "") if identity_row is not None else "")),
            "historical_team": historical_team,
            "current_team": current_team,
            "projection_team": current_team if status == "READY" else "",
            "roster_status": item.get("roster_status", ""),
            "depth_chart_role": item.get("depth_chart_role", ""),
            "source": item.get("source", ""),
            "updated_at": item.get("updated_at", ""),
            "manual_override": override_applied,
            "team_mapping_status": status,
            "validation_status": validation,
            "notes": " ".join(reasons),
        })
    return pd.DataFrame(rows, columns=MAP_COLUMNS)


def build_current_roster_map(roster_dir: Path | None = None, identity_path: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    roster_dir = roster_dir or project_path("data", "gates", "rosters")
    identity_path = identity_path or output_path("identity/player_identity_crosswalk.csv")
    roster_paths, override_paths = discover_real_inputs(roster_dir)
    rosters = _read_many(roster_paths)
    overrides = _read_many(override_paths)
    identity = pd.read_csv(identity_path, low_memory=False) if identity_path.exists() else pd.DataFrame()
    mapped = build_map_from_frames(rosters, overrides, identity)
    needs_review = mapped[mapped["team_mapping_status"].ne("READY")].copy() if not mapped.empty else mapped.copy()
    counts = mapped["team_mapping_status"].value_counts() if not mapped.empty else pd.Series(dtype=int)
    overall = "NEEDS DATA" if not roster_paths or mapped.empty else ("BLOCKED" if counts.get("BLOCKED", 0) else ("NEEDS REVIEW" if counts.get("NEEDS REVIEW", 0) or counts.get("NEEDS DATA", 0) else "READY"))
    status = pd.DataFrame([{
        "status": overall,
        "real_roster_files": len(roster_paths),
        "override_files": len(override_paths),
        "roster_rows_loaded": len(mapped),
        "ready_rows": int(counts.get("READY", 0)),
        "needs_review_rows": int(counts.get("NEEDS REVIEW", 0)),
        "needs_data_rows": int(counts.get("NEEDS DATA", 0)),
        "blocked_rows": int(counts.get("BLOCKED", 0)),
        "changed_team_rows": int(mapped["notes"].astype(str).str.contains("TEAM_CHANGE:").sum()) if not mapped.empty else 0,
        "manual_overrides": int(mapped["manual_override"].map(_truthy).sum()) if not mapped.empty else 0,
        "templates_ignored": True,
        "notes": "No real current roster input found; template files do not count as data." if overall == "NEEDS DATA" else "Current roster map built from non-template inputs.",
    }])
    mapped.to_csv(output_path("roster/current_roster_map.csv"), index=False)
    status.to_csv(output_path("roster/current_roster_map_status.csv"), index=False)
    needs_review.to_csv(output_path("roster/current_roster_needs_review.csv"), index=False)
    return mapped, status, needs_review


def main() -> None:
    mapped, status, review = build_current_roster_map()
    print(f"current_roster_map: {len(mapped):,} rows")
    print(f"current_roster_needs_review: {len(review):,} rows")
    print(f"current_roster_map_status: {status['status'].iloc[0]}")
    print("template_files_count_as_data: False")


if __name__ == "__main__":
    main()
