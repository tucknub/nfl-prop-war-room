from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping

from src.knockout import engine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _lineup_slot_id(value: object) -> int:
    if value is None or str(value).strip() == "":
        return -1
    return int(value)


def _plain_roster(snapshot: Mapping[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "player": str(row.get("player") or "").strip(),
            "position": str(row.get("position") or "").strip(),
            "nfl_team": str(row.get("nfl_team") or "").strip(),
        }
        for row in snapshot.get("roster") or []
    ]


def _plain_available_players(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in snapshot.get("available_players") or []:
        player = str(raw.get("player") or "").strip()
        position = engine.canonical_position(raw.get("position"))
        nfl_team = str(raw.get("nfl_team") or "").strip().upper()
        if not player or position not in engine.VALID_POSITIONS or not nfl_team:
            continue
        rows.append(
            {
                "player": player,
                "position": position,
                "nfl_team": nfl_team,
                "espn_player_id": str(raw.get("espn_player_id") or "").strip(),
                "injury_status": str(raw.get("injury_status") or "").strip(),
                "percent_owned": raw.get("percent_owned"),
                "projected_points": raw.get("projected_points"),
            }
        )
    return rows


def _reconcile_detected_elimination(
    updated: dict[str, Any],
    snapshot: Mapping[str, Any],
) -> None:
    detected = snapshot.get("detected_elimination")
    if not isinstance(detected, Mapping):
        return

    week = int(detected.get("week") or 0)
    source_week = int(snapshot.get("current_week") or 0)
    team = str(detected.get("team") or "").strip()
    if week < 1 or source_week <= week or not team:
        return

    same_week = [
        row
        for row in updated.get("eliminations") or []
        if int(row.get("week", -1)) == week
    ]
    if same_week:
        if any(
            str(row.get("team") or "").strip().casefold() != team.casefold()
            for row in same_week
        ):
            raise ValueError(
                f"ESPN detected a different Week {week} elimination than the stored Knockout ledger."
            )
    else:
        updated.setdefault("eliminations", []).append({"week": week, "team": team})

    if not any(
        int(row.get("week", -1)) == week
        for row in updated.get("weekly_results") or []
    ):
        user_score = detected.get("user_score")
        if user_score is not None:
            updated.setdefault("weekly_results", []).append(
                {
                    "week": week,
                    "user_score": float(user_score),
                    "user_eliminated": bool(detected.get("user_eliminated")),
                }
            )

    if not any(
        int(row.get("week", -1)) == week
        for row in updated.get("released_rosters") or []
    ):
        players = list(detected.get("players") or [])
        expected = int((updated.get("league") or {}).get("roster_size", 14))
        if len(players) == expected:
            normalized = engine.validate_roster(players, roster_size=expected)
            updated.setdefault("released_rosters", []).append(
                {
                    "week": week,
                    "team": team,
                    "players": normalized,
                }
            )

    if bool(detected.get("user_eliminated")):
        updated["status"] = "ELIMINATED"


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
    discovered_relink = bool(snapshot.get("discovered_relink"))
    expected_name = str(league.get("name") or "").strip().casefold()
    source_name = str(snapshot.get("league_name") or "").strip().casefold()
    relink_allowed = bool(
        discovered_relink
        and expected_name
        and source_name == expected_name
    )

    if expected_league_id and source_league_id != expected_league_id and not relink_allowed:
        raise ValueError(
            f"ESPN returned league {source_league_id or 'unknown'}; "
            f"Knockout is configured for league {expected_league_id}."
        )

    expected_team_id = int(league.get("espn_team_id") or 0)
    source_team_id = int(snapshot.get("team_id") or 0)
    if expected_team_id and source_team_id != expected_team_id and not relink_allowed:
        raise ValueError(
            f"ESPN returned team {source_team_id or 'unknown'}; "
            f"Knockout is configured for team {expected_team_id}."
        )
    if relink_allowed and source_team_id <= 0:
        raise ValueError("Discovered ESPN league did not resolve an authenticated team.")

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
    if bool(snapshot.get("discovered_relink")):
        league["espn_league_id"] = str(snapshot.get("league_id") or "").strip()
        league["espn_team_id"] = int(snapshot.get("team_id") or 0)
    updated["league"] = league

    detected_rows = snapshot.get("detected_eliminations")
    if isinstance(detected_rows, list):
        for detected in detected_rows:
            if not isinstance(detected, Mapping):
                continue
            replay = dict(snapshot)
            replay["detected_elimination"] = detected
            _reconcile_detected_elimination(updated, replay)
    else:
        _reconcile_detected_elimination(updated, snapshot)

    existing = dict(updated.get("espn_connection") or {})
    envelope = credential_envelope or str(existing.get("credential_envelope") or "")
    available_players = (
        _plain_available_players(snapshot)
        if "available_players" in snapshot
        else list(existing.get("available_players") or [])
    )
    league_week_scores = (
        [dict(row) for row in snapshot.get("league_week_scores") or []]
        if "league_week_scores" in snapshot
        else list(existing.get("league_week_scores") or [])
    )
    roster_player_metrics = (
        _plain_available_players({"available_players": snapshot.get("roster_player_metrics") or []})
        if "roster_player_metrics" in snapshot
        else list(existing.get("roster_player_metrics") or [])
    )
    league_faab = (
        [dict(row) for row in snapshot.get("league_faab") or []]
        if "league_faab" in snapshot
        else list(existing.get("league_faab") or [])
    )
    detected_elimination = (
        dict(snapshot.get("detected_elimination") or {})
        if "detected_elimination" in snapshot
        else dict(existing.get("detected_elimination") or {})
    )
    detected_eliminations = (
        [dict(row) for row in snapshot.get("detected_eliminations") or [] if isinstance(row, Mapping)]
        if "detected_eliminations" in snapshot
        else list(existing.get("detected_eliminations") or [])
    )
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
        "league_context_error": str(snapshot.get("league_context_error") or "").strip(),
        "available_players": available_players,
        "roster_player_metrics": roster_player_metrics,
        "league_faab": league_faab,
        "league_week_scores": league_week_scores,
        "detected_elimination": detected_elimination,
        "detected_eliminations": detected_eliminations,
        "roster_details": [
            {
                "player": str(row.get("player") or "").strip(),
                "position": str(row.get("position") or "").strip(),
                "nfl_team": str(row.get("nfl_team") or "").strip(),
                "lineup_role": str(row.get("lineup_role") or "").strip(),
                "lineup_slot_id": _lineup_slot_id(row.get("lineup_slot_id")),
                "injury_status": str(row.get("injury_status") or "").strip(),
            }
            for row in snapshot.get("roster") or []
        ],
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
