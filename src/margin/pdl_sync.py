from __future__ import annotations

import json
from copy import deepcopy
from typing import Any
from urllib.request import Request, urlopen

from . import championship
from . import live_engine


DEFAULT_PDL_URL = "https://pdl.kingtuddy.com/pdl-data.json"
DEFAULT_ENTRANT = "Ricky T."


def fetch_pdl_data(url: str = DEFAULT_PDL_URL, timeout: int = 15) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "Cache-Control": "no-cache",
            "User-Agent": "PropWar-PDL-Sync/1.0",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("PDL payload must be one JSON object")
    return payload


def _team_map(payload: dict[str, Any]) -> dict[str, str]:
    teams = payload.get("teams")
    if not isinstance(teams, dict) or not teams:
        raise ValueError("PDL teams mapping is missing")
    mapped: dict[str, str] = {}
    aliases = {"LAR": "LA", "WSH": "WAS"}
    for display_name, code in teams.items():
        canonical = aliases.get(str(code).upper(), str(code).upper())
        if canonical not in championship.VALID_TEAMS:
            raise ValueError(f"PDL team mapping is invalid: {display_name} -> {code}")
        mapped[str(display_name)] = canonical
    return mapped


def _final_weeks(entry: dict[str, Any], completed_week: int, team_map: dict[str, str]) -> list[dict[str, Any]]:
    weeks = entry.get("weeks") or []
    finals = [w for w in weeks if str(w.get("status", "")).upper() == "FINAL"]
    finals = [w for w in finals if int(w.get("week", 0)) <= completed_week]
    by_week = {int(w["week"]): w for w in finals}
    expected = set(range(1, completed_week + 1))
    if set(by_week) != expected or len(finals) != completed_week:
        raise ValueError(f"{entry.get('name')}: finalized weeks do not match 1..{completed_week}")

    normalized: list[dict[str, Any]] = []
    used: set[str] = set()
    for week in range(1, completed_week + 1):
        row = by_week[week]
        team_name = str(row.get("team", ""))
        if team_name not in team_map:
            raise ValueError(f"{entry.get('name')}: unknown PDL team {team_name}")
        team = team_map[team_name]
        if team in used:
            raise ValueError(f"{entry.get('name')}: reused team {team}")
        try:
            margin = float(row["margin"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"{entry.get('name')}: Week {week} margin is invalid") from exc
        used.add(team)
        normalized.append({"week": week, "team": team, "actual_margin": margin})
    return normalized


def _pending_pick(entry: dict[str, Any], current_week: int, team_map: dict[str, str]) -> str | None:
    rows = [w for w in (entry.get("weeks") or []) if int(w.get("week", 0)) == current_week]
    rows = [w for w in rows if str(w.get("status", "")).upper() != "FINAL"]
    if not rows:
        return None
    if len(rows) != 1:
        raise ValueError(f"{entry.get('name')}: multiple Week {current_week} pending picks")
    team_name = str(rows[0].get("team", ""))
    if team_name not in team_map:
        raise ValueError(f"{entry.get('name')}: unknown pending PDL team {team_name}")
    return team_map[team_name]


def reconcile_state(
    stored_state: dict[str, Any],
    payload: dict[str, Any],
    *,
    entrant_name: str = DEFAULT_ENTRANT,
    source_url: str = DEFAULT_PDL_URL,
) -> dict[str, Any]:
    schema = str(payload.get("schema_version", ""))
    if not schema.startswith("pdl_season_"):
        raise ValueError(f"Unsupported PDL schema: {schema or 'missing'}")
    league = payload.get("league") or {}
    season = int(league.get("season", 0))
    if season != live_engine.SEASON:
        raise ValueError(f"PDL season {season} does not match PropWar {live_engine.SEASON}")
    completed_week = int(league.get("completed_week", 0))
    if completed_week < 0 or completed_week > 18:
        raise ValueError(f"Invalid PDL completed_week={completed_week}")
    current_week = 18 if completed_week >= 18 else completed_week + 1

    team_map = _team_map(payload)
    active = [e for e in (payload.get("entrants") or []) if str(e.get("status", "")).upper() == "ACTIVE"]
    names = [str(e.get("name", "")).strip() for e in active]
    if len(names) != len(set(names)):
        raise ValueError("PDL active entrant names must be unique")
    hero = next((e for e in active if str(e.get("name")) == entrant_name), None)
    if hero is None:
        raise ValueError(f"PDL entrant {entrant_name!r} is not active")

    hero_results = _final_weeks(hero, completed_week, team_map)
    prior_results = {
        (int(row.get("week", 0)), str(row.get("team", ""))): row
        for row in (stored_state.get("weekly_results") or [])
    }
    for row in hero_results:
        prior = prior_results.get((int(row["week"]), str(row["team"]))) or {}
        if prior.get("completed_at_utc"):
            row["completed_at_utc"] = prior["completed_at_utc"]
    used_teams = [row["team"] for row in hero_results]
    cumulative_score = float(sum(row["actual_margin"] for row in hero_results))

    opponents: list[dict[str, Any]] = []
    for entry in active:
        name = str(entry.get("name", "")).strip()
        if name == entrant_name:
            continue
        results = _final_weeks(entry, completed_week, team_map)
        opponents.append(
            {
                "id": f"pdl:{name}",
                "name": name,
                "cumulative_score": float(sum(row["actual_margin"] for row in results)),
                "used_teams": [row["team"] for row in results],
            }
        )

    updated = deepcopy(stored_state)
    updated["schema_version"] = str(updated.get("schema_version") or "margin_live_state_v1")
    updated["season"] = season
    updated["current_week"] = current_week
    updated["completed_week"] = completed_week
    updated["cumulative_score"] = cumulative_score
    updated["used_teams"] = used_teams
    updated["weekly_results"] = hero_results
    updated["season_complete"] = bool(completed_week >= 18)

    pool = dict(updated.get("pool") or {})
    pool.update(
        {
            "name": str(league.get("name") or "Point Differential League"),
            "size": len(active),
            "payout_structure": str(pool.get("payout_structure") or "winner_take_all"),
        }
    )
    updated["pool"] = pool
    updated["opponents"] = opponents

    pending_pick = _pending_pick(hero, current_week, team_map) if completed_week < 18 else None
    previous_decision = dict(stored_state.get("current_decision") or {})
    preserve_private_commit = (
        int(stored_state.get("current_week", 0) or 0) == current_week
        and str(previous_decision.get("status")) == "COMMITTED"
        and previous_decision.get("committed_pick")
    )
    if pending_pick:
        updated["current_decision"] = {
            **previous_decision,
            "status": "COMMITTED",
            "committed_pick": pending_pick,
            "reason": "Synced from the authoritative PDL entrant ledger.",
        }
    elif preserve_private_commit:
        updated["current_decision"] = previous_decision
    else:
        updated["current_decision"] = {
            "status": "SEASON_COMPLETE" if completed_week >= 18 else "NEEDS_REFRESH",
            "provisional_pick": None,
            "committed_pick": None,
            "anchor": None,
            "market_snapshot_utc": None,
            "current_spread": None,
            "calibrated_expected_margin": None,
            "p_loss": None,
            "p_win20": None,
            "reason": "PDL ledger synchronized; refresh live markets for the current recommendation.",
        }

    if pending_pick and pending_pick in set(used_teams):
        raise ValueError(f"{entrant_name}: pending pick {pending_pick} was already used")

    updated["pdl_sync"] = {
        "source_url": source_url,
        "schema_version": schema,
        "entrant": entrant_name,
        "data_fingerprint_sha256": payload.get("data_fingerprint_sha256"),
        "league_updated": league.get("updated"),
    }
    live_engine.validate_state(updated)
    return updated


def fetch_and_reconcile(
    stored_state: dict[str, Any],
    *,
    url: str = DEFAULT_PDL_URL,
    entrant_name: str = DEFAULT_ENTRANT,
    timeout: int = 15,
) -> dict[str, Any]:
    payload = fetch_pdl_data(url=url, timeout=timeout)
    return reconcile_state(
        stored_state,
        payload,
        entrant_name=entrant_name,
        source_url=url,
    )
