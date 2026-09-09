from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping

from src.knockout import engine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _plain_roster(snapshot: Mapping[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "player": str(row.get("player") or "").strip(),
            "position": str(row.get("position") or "").strip(),
            "nfl_team": str(row.get("nfl_team") or "").strip(),
        }
        for row in snapshot.get("roster") or []
    ]


def validate_snapshot_for_knockout(
    state: Mapping[str, Any],
    snapshot: Mapping[str, Any],
) -> list[dict[str, str]]:
    if str(snapshot.get("provider") or "").upper() != "ESPN":
        raise ValueError("Knockout ESPN sync requires an ESPN snapshot.")
    if int(snapshot.get("season") or 0) != int(state.get("season") or 0):
        raise ValueError("ESPN season does not match the Knockout season.")

    league = state.get("league") or {}

    expected_league_id = str(league.get("espn_league_id") or "").strip()
    source_league_id = str(snapshot.get("league_id") or "").strip()
    if expected_league_id and source_league_id != expected_league_id:
        raise ValueError(
            f"ESPN returned league {source_league_id or 'unknown'}; "
            f"Knockout is configured for league {expected_league_id}."
        )

    expected_team_id = int(league.get("espn_team_id") or 0)
    source_team_id = int(snapshot.get("team_id") or 0)
    if expected_team_id and source_team_id != expected_team_id:
        raise ValueError(
            f"ESPN returned team {source_team_id or 'unknown'}; "
            f"Knockout is configured for team {expected_team_id}."
        )

    expected_teams = int(league.get("teams") or 0)
    team_count = int(snapshot.get("team_count") or 0)
    if expected_teams and team_count and team_count != expected_teams:
        raise ValueError(
            f"ESPN league has {team_count} teams; Knockout expects {expected_teams}."
        )

    expected_roster = int(league.get("roster_size") or 14)
    return engine.validate_roster(
        _plain_roster(snapshot),
        roster_size=expected_roster,
        require_startable=True,
    )


def apply_espn_snapshot(
    state: dict[str, Any],
    snapshot: Mapping[str, Any],
    *,
    credential_envelope: str | None = None,
    synced_at_utc: str | None = None,
) -> dict[str, Any]:
    engine.validate_state(state)
    normalized_roster = validate_snapshot_for_knockout(state, snapshot)

    updated = deepcopy(state)
    updated["roster"] = normalized_roster
    if str(updated.get("status") or "") in {"PRE_DRAFT", "AWAITING_ROSTER"}:
        updated["status"] = "ACTIVE"

    source_week = int(snapshot.get("current_week") or 0)
    if 1 <= source_week <= 17 and str(updated.get("status")) not in {"ELIMINATED", "CHAMPION"}:
        updated["current_week"] = source_week

    faab_remaining = snapshot.get("faab_remaining")
    if faab_remaining is not None:
        updated["faab_remaining"] = int(faab_remaining)

    league = dict(updated.get("league") or {})
    if str(snapshot.get("league_name") or "").strip():
        league["name"] = str(snapshot["league_name"]).strip()
    updated["league"] = league

    existing = dict(updated.get("espn_connection") or {})
    envelope = credential_envelope or str(existing.get("credential_envelope") or "")
    connection = {
        "provider": "ESPN",
        "mode": "PRIVATE_COOKIE_READ_ONLY",
        "league_id": str(snapshot.get("league_id") or "").strip(),
        "league_name": str(snapshot.get("league_name") or "").strip(),
        "team_id": int(snapshot.get("team_id") or 0),
        "team_name": str(snapshot.get("team_name") or "").strip(),
        "last_synced_at_utc": synced_at_utc or _now_iso(),
        "source_week": source_week,
        "source_faab_remaining": snapshot.get("faab_remaining"),
        "source_current_score": snapshot.get("current_score"),
        "credential_envelope": envelope,
    }
    if not envelope:
        raise ValueError("Secure ESPN credential envelope is required for private sync.")
    updated["espn_connection"] = connection

    engine.validate_state(updated)
    return updated


def disconnect_espn(state: dict[str, Any]) -> dict[str, Any]:
    engine.validate_state(state)
    updated = deepcopy(state)
    updated.pop("espn_connection", None)
    engine.validate_state(updated)
    return updated
