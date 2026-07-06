from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

from src.common import output_path, project_path
from src.load.build_identity_crosswalk import canonical_team, normalize_player_name
from src.markets.market_registry import market_registry_df
from src.models.odds_utils import (
    american_to_implied_probability,
    calculate_edge,
    normalize_market_key,
    validate_price,
)


COLUMNS = [
    "player_id",
    "player_name",
    "normalized_player_name",
    "team",
    "opponent",
    "market_key",
    "market_display_name",
    "sportsbook",
    "line",
    "over_odds",
    "under_odds",
    "implied_over_probability",
    "implied_under_probability",
    "model_projection",
    "model_over_probability",
    "model_under_probability",
    "edge_over",
    "edge_under",
    "best_side",
    "best_edge",
    "source",
    "odds_timestamp",
    "manual_override",
    "odds_mapping_status",
    "validation_status",
    "notes",
]


def truthy(value) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "approved"}


def is_blank(value) -> bool:
    return pd.isna(value) or str(value).strip() == ""


def discover_real_inputs(folder: Path) -> tuple[list[Path], list[Path]]:
    folder.mkdir(parents=True, exist_ok=True)
    files = sorted(folder.glob("*.csv"))
    real = [path for path in files if "template" not in path.name.lower()]
    overrides = [path for path in real if "override" in path.name.lower()]
    inputs = [path for path in real if "override" not in path.name.lower()]
    return inputs, overrides


def read_many(paths: Iterable[Path]) -> pd.DataFrame:
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


def active_market_keys() -> set[str]:
    registry = market_registry_df()
    return set(registry[registry["active"] == True]["market_key"].astype(str))  # noqa: E712


def identity_candidates(identity: pd.DataFrame, player_id: str, normalized_name: str) -> pd.DataFrame:
    if identity.empty:
        return pd.DataFrame()
    if player_id:
        exact = identity[identity["player_id"].fillna("").astype(str).str.strip().eq(player_id)]
        if not exact.empty:
            return exact
    return identity[identity["normalized_player_name"].fillna("").astype(str).eq(normalized_name)]


def _gate_lookup(frame: pd.DataFrame, id_col: str, status_col: str) -> dict[str, str]:
    if frame.empty or id_col not in frame.columns or status_col not in frame.columns:
        return {}
    return {str(row[id_col]).strip(): str(row[status_col]) for _, row in frame.iterrows()}


def _probability_lookup() -> dict[tuple[str, str, float], dict[str, float]]:
    lookup: dict[tuple[str, str, float], dict[str, float]] = {}
    paths = {
        "receptions": "market_edges/receptions_line_ladder.csv",
        "receiving_yards": "market_edges/receiving_yards_line_ladder.csv",
        "rushing_yards": "market_edges/rushing_yards_line_ladder.csv",
        "carries": "market_edges/carries_line_ladder.csv",
        "pass_attempts": "market_edges/pass_attempts_line_ladder.csv",
        "completions": "market_edges/completions_line_ladder.csv",
        "passing_yards": "market_edges/passing_yards_line_ladder.csv",
    }
    for market_key, relative in paths.items():
        path = output_path(relative)
        if not path.exists():
            continue
        frame = pd.read_csv(path, low_memory=False)
        if frame.empty or "line" not in frame.columns:
            continue
        for _, row in frame.iterrows():
            player_key = str(row.get("player_id") or row.get("player_name") or "").strip()
            team = canonical_team(row.get("team", ""))
            line = pd.to_numeric(row.get("line"), errors="coerce")
            if not player_key or pd.isna(line):
                continue
            lookup[(market_key, player_key, float(line))] = {
                "model_projection": pd.to_numeric(row.get("calibrated_projection"), errors="coerce"),
                "model_over_probability": pd.to_numeric(row.get("model_over_probability"), errors="coerce"),
                "model_under_probability": pd.to_numeric(row.get("model_under_probability"), errors="coerce"),
            }
            if team:
                lookup[(market_key, f"{player_key}|{team}", float(line))] = lookup[(market_key, player_key, float(line))]
    return lookup


def _override_lookup(overrides: pd.DataFrame) -> dict[tuple[str, str, str], pd.Series]:
    if overrides.empty:
        return {}
    out = overrides.copy()
    for col in ["player_id", "player_name", "team", "market_key", "sportsbook", "approved"]:
        if col not in out.columns:
            out[col] = ""
    out["player_id"] = out["player_id"].fillna("").astype(str).str.strip()
    out["normalized_player_name"] = out["player_name"].map(normalize_player_name)
    out["market_key"] = out["market_key"].map(normalize_market_key)
    out["sportsbook"] = out["sportsbook"].fillna("").astype(str).str.strip().str.lower()
    lookup = {}
    for _, row in out.iterrows():
        key_id = row["player_id"] or "name:" + row["normalized_player_name"]
        lookup[(key_id, row["market_key"], row["sportsbook"])] = row
    return lookup


def _freshness_review(timestamp) -> bool:
    parsed = pd.to_datetime(timestamp, errors="coerce", utc=True)
    if pd.isna(parsed):
        return True
    return (datetime.now(timezone.utc) - parsed.to_pydatetime()).days > 7


def build_map_from_frames(
    odds: pd.DataFrame,
    overrides: pd.DataFrame,
    identity: pd.DataFrame,
    roster: pd.DataFrame,
    roles: pd.DataFrame,
    injuries: pd.DataFrame,
    probability_lookup: dict[tuple[str, str, float], dict[str, float]] | None = None,
) -> pd.DataFrame:
    if odds.empty:
        return pd.DataFrame(columns=COLUMNS)
    data = odds.copy()
    base = [
        "player_id",
        "player_name",
        "team",
        "opponent",
        "market_key",
        "market_display_name",
        "sportsbook",
        "line",
        "over_odds",
        "under_odds",
        "odds_timestamp",
        "source",
        "source_url",
        "manual_override",
        "notes",
    ]
    for col in base:
        if col not in data.columns:
            data[col] = ""
    data["player_id"] = data["player_id"].fillna("").astype(str).str.strip()
    data["player_name"] = data["player_name"].fillna("").astype(str).str.strip()
    data["normalized_player_name"] = data["player_name"].map(normalize_player_name)
    data["team"] = data["team"].map(canonical_team)
    data["opponent"] = data["opponent"].map(canonical_team)
    data["market_key"] = data["market_key"].map(normalize_market_key)
    override_map = _override_lookup(overrides)
    active = active_market_keys()
    roster_status = _gate_lookup(roster, "player_id", "team_mapping_status")
    role_status = _gate_lookup(roles, "player_id", "role_mapping_status")
    injury_status = _gate_lookup(injuries, "player_id", "injury_mapping_status")
    probability_lookup = probability_lookup if probability_lookup is not None else _probability_lookup()
    rows = []
    for _, row in data.iterrows():
        player_id = row["player_id"]
        team = canonical_team(row["team"])
        sportsbook = str(row["sportsbook"]).strip()
        market_key = normalize_market_key(row["market_key"])
        override = override_map.get((player_id or "name:" + row["normalized_player_name"], market_key, sportsbook.lower()))
        approved_override = bool(override is not None and truthy(override.get("approved", False)))
        line = row["line"]
        over_odds = row["over_odds"]
        under_odds = row["under_odds"]
        if approved_override:
            line = override.get("override_line") if str(override.get("override_line", "")).strip() else line
            over_odds = override.get("override_over_odds") if str(override.get("override_over_odds", "")).strip() else over_odds
            under_odds = override.get("override_under_odds") if str(override.get("override_under_odds", "")).strip() else under_odds
        line_num = pd.to_numeric(line, errors="coerce")
        implied_over = american_to_implied_probability(over_odds)
        implied_under = american_to_implied_probability(under_odds)
        candidates = identity_candidates(identity, player_id, row["normalized_player_name"])
        notes: list[str] = []
        review = False
        blocked = False
        validation = "PASS"
        if market_key not in active:
            blocked = True
            validation = "INVALID_MARKET_KEY"
            notes.append("market_key is not an active supported market.")
        if candidates.empty:
            blocked = True
            validation = "UNMATCHED_PLAYER"
            notes.append("Odds row cannot be matched to identity crosswalk.")
        elif not player_id and len(candidates["player_id"].dropna().astype(str).unique()) > 1:
            blocked = True
            validation = "DUPLICATE_PLAYER_NAME"
            notes.append("Name-only odds row matches multiple players.")
        elif not player_id:
            review = True
            validation = "MISSING_PLAYER_ID"
            notes.append("Missing player_id; name-only odds row requires review.")
            player_id = str(candidates["player_id"].iloc[0])
        if pd.isna(line_num) or float(line_num) < 0:
            blocked = True
            validation = "INVALID_LINE"
            notes.append("Line must be a non-negative number.")
        one_side_missing = is_blank(over_odds) or is_blank(under_odds)
        if one_side_missing:
            review = True
            validation = "MISSING_ODDS_SIDE" if validation == "PASS" else validation
            notes.append("One odds side is missing.")
        if not is_blank(over_odds) and not validate_price(over_odds):
            blocked = True
            validation = "INVALID_ODDS"
            notes.append("Over odds are invalid American odds.")
        if not is_blank(under_odds) and not validate_price(under_odds):
            blocked = True
            validation = "INVALID_ODDS"
            notes.append("Under odds are invalid American odds.")
        if not team or not str(row["opponent"]).strip():
            review = True
            validation = "MISSING_TEAM_CONTEXT" if validation == "PASS" else validation
            notes.append("Team and opponent are required for live odds matching.")
        if not sportsbook:
            review = True
            validation = "UNKNOWN_SPORTSBOOK" if validation == "PASS" else validation
            notes.append("Sportsbook is required.")
        if _freshness_review(row["odds_timestamp"]):
            review = True
            validation = "STALE_OR_MISSING_TIMESTAMP" if validation == "PASS" else validation
            notes.append("Odds timestamp is stale or missing.")
        if truthy(row["manual_override"]) and not approved_override:
            review = True
            validation = "OVERRIDE_NOT_APPROVED" if validation == "PASS" else validation
            notes.append("Manual odds override is not approved.")
        for gate_name, gate_status in [("roster", roster_status), ("role", role_status), ("injury", injury_status)]:
            status = gate_status.get(player_id)
            if status and status != "READY":
                blocked = True
                validation = f"{gate_name.upper()}_BLOCKER"
                notes.append(f"{gate_name} map status is {status}.")
        prob = {}
        if not pd.isna(line_num):
            line_float = float(line_num)
            prob = probability_lookup.get((market_key, f"{player_id}|{team}", line_float)) or probability_lookup.get((market_key, player_id, line_float)) or probability_lookup.get((market_key, row["player_name"], line_float)) or {}
        model_over = prob.get("model_over_probability", pd.NA)
        model_under = prob.get("model_under_probability", pd.NA)
        edge_over = calculate_edge(model_over, implied_over)
        edge_under = calculate_edge(model_under, implied_under)
        best_side, best_edge = "", pd.NA
        if edge_over is not None and (edge_under is None or edge_over >= edge_under):
            best_side, best_edge = "Over", edge_over
        elif edge_under is not None:
            best_side, best_edge = "Under", edge_under
        status = "BLOCKED" if blocked else ("NEEDS REVIEW" if review else "READY")
        rows.append(
            {
                "player_id": player_id,
                "player_name": row["player_name"],
                "normalized_player_name": row["normalized_player_name"],
                "team": team,
                "opponent": canonical_team(row["opponent"]),
                "market_key": market_key,
                "market_display_name": row["market_display_name"],
                "sportsbook": sportsbook,
                "line": "" if pd.isna(line_num) else float(line_num),
                "over_odds": over_odds,
                "under_odds": under_odds,
                "implied_over_probability": implied_over,
                "implied_under_probability": implied_under,
                "model_projection": prob.get("model_projection", pd.NA),
                "model_over_probability": model_over,
                "model_under_probability": model_under,
                "edge_over": edge_over,
                "edge_under": edge_under,
                "best_side": best_side,
                "best_edge": best_edge,
                "source": row["source"],
                "odds_timestamp": row["odds_timestamp"],
                "manual_override": approved_override,
                "odds_mapping_status": status,
                "validation_status": validation if validation != "PASS" or status != "READY" else "PASS",
                "notes": " ".join(notes) if notes else ("Approved odds override applied." if approved_override else "Odds row validated."),
            }
        )
    return pd.DataFrame(rows, columns=COLUMNS)


def build_market_odds_map(odds_dir: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    odds_dir = odds_dir or project_path("data", "gates", "odds")
    input_paths, override_paths = discover_real_inputs(odds_dir)
    odds = read_many(input_paths)
    overrides = read_many(override_paths)
    identity_path = output_path("identity/player_identity_crosswalk.csv")
    roster_path = output_path("roster/current_roster_map.csv")
    role_path = output_path("roles/current_role_map.csv")
    injury_path = output_path("injuries/current_injury_map.csv")
    identity = pd.read_csv(identity_path, low_memory=False) if identity_path.exists() else pd.DataFrame()
    roster = pd.read_csv(roster_path, low_memory=False) if roster_path.exists() else pd.DataFrame()
    roles = pd.read_csv(role_path, low_memory=False) if role_path.exists() else pd.DataFrame()
    injuries = pd.read_csv(injury_path, low_memory=False) if injury_path.exists() else pd.DataFrame()
    mapped = build_map_from_frames(odds, overrides, identity, roster, roles, injuries)
    review = mapped[mapped["odds_mapping_status"].ne("READY")].copy() if not mapped.empty else mapped.copy()
    counts = mapped["odds_mapping_status"].value_counts() if not mapped.empty else pd.Series(dtype=int)
    overall = "NEEDS DATA" if not input_paths or mapped.empty else ("BLOCKED" if counts.get("BLOCKED", 0) else ("NEEDS REVIEW" if counts.get("NEEDS REVIEW", 0) else "READY"))
    status = pd.DataFrame(
        [
            {
                "status": overall,
                "real_odds_files": len(input_paths),
                "override_files": len(override_paths),
                "odds_rows_loaded": len(mapped),
                "ready_rows": int(counts.get("READY", 0)),
                "needs_review_rows": int(counts.get("NEEDS REVIEW", 0)),
                "needs_data_rows": 0,
                "blocked_rows": int(counts.get("BLOCKED", 0)),
                "active_markets_covered": int(mapped["market_key"].nunique()) if not mapped.empty else 0,
                "sportsbooks_loaded": int(mapped["sportsbook"].nunique()) if not mapped.empty else 0,
                "manual_overrides": int(mapped["manual_override"].map(truthy).sum()) if not mapped.empty else 0,
                "templates_ignored": True,
                "notes": "No real current odds input found; template files do not count as data." if overall == "NEEDS DATA" else "Current market odds map built from non-template inputs.",
            }
        ]
    )
    mapped.to_csv(output_path("odds/current_market_odds_map.csv"), index=False)
    status.to_csv(output_path("odds/current_market_odds_status.csv"), index=False)
    review.to_csv(output_path("odds/current_market_odds_needs_review.csv"), index=False)
    return mapped, status, review


def main() -> None:
    mapped, status, review = build_market_odds_map()
    print(f"current_market_odds_map: {len(mapped):,} rows")
    print(f"current_market_odds_needs_review: {len(review):,} rows")
    print(f"current_market_odds_status: {status.status.iloc[0]}")
    print("template_files_count_as_data: False")


if __name__ == "__main__":
    main()
