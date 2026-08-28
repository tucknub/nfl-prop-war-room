from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable


VALID_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DST"}
FLEX_POSITIONS = {"RB", "WR", "TE"}
REQUIRED_STARTERS = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DST": 1}
FIT_PRIORITY = {"URGENT": 0, "HIGH": 1, "MEDIUM": 2, "DEPTH": 3, "LOW": 4}


def canonical_position(value: object) -> str:
    return str(value or "").strip().upper().replace("D/ST", "DST").replace("DEF", "DST")


def _lineup_errors(roster: Iterable[dict[str, Any]]) -> list[str]:
    rows = list(roster)
    counts = {pos: sum(canonical_position(row.get("position")) == pos for row in rows) for pos in VALID_POSITIONS}
    errors: list[str] = []
    for pos, required in REQUIRED_STARTERS.items():
        if counts[pos] < required:
            errors.append(f"need {required} {pos}, found {counts[pos]}")
    flex_pool = sum(counts[pos] for pos in FLEX_POSITIONS)
    if flex_pool < 6:  # 2 RB + 2 WR + 1 TE + 1 FLEX
        errors.append(f"need 6 RB/WR/TE players to fill starters plus FLEX, found {flex_pool}")
    return errors


def lineup_readiness(roster: Iterable[dict[str, Any]]) -> dict[str, Any]:
    errors = _lineup_errors(roster)
    return {"ready": not errors, "errors": errors}


def validate_roster(
    roster: Iterable[dict[str, Any]],
    *,
    roster_size: int = 14,
    require_startable: bool = False,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in roster:
        player = str(raw.get("player", "")).strip()
        position = canonical_position(raw.get("position"))
        nfl_team = str(raw.get("nfl_team", "")).strip().upper()
        if not player:
            raise ValueError("every roster row needs a player name")
        if player.casefold() in seen:
            raise ValueError(f"duplicate roster player: {player}")
        if position not in VALID_POSITIONS:
            raise ValueError(f"invalid position for {player}: {position or 'missing'}")
        if not nfl_team:
            raise ValueError(f"missing NFL team for {player}")
        seen.add(player.casefold())
        rows.append({"player": player, "position": position, "nfl_team": nfl_team})

    if len(rows) != int(roster_size):
        raise ValueError(f"roster must contain exactly {int(roster_size)} players; received {len(rows)}")

    if require_startable:
        errors = _lineup_errors(rows)
        if errors:
            raise ValueError(f"roster cannot fill required starters: {'; '.join(errors)}")
    return rows


def validate_state(state: dict[str, Any]) -> dict[str, Any]:
    if str(state.get("schema_version")) != "knockout_live_state_v1":
        raise ValueError("unsupported Knockout state schema")
    if int(state.get("season", 0)) != 2026:
        raise ValueError("Knockout V1 currently supports the 2026 season")

    league = state.get("league") or {}
    if int(league.get("teams", 0)) != 18:
        raise ValueError("Knockout league must contain 18 teams")
    if bool(league.get("trades_allowed", True)):
        raise ValueError("Knockout league is trade-free; trades_allowed must be false")
    if str(league.get("scoring", "")).upper() != "FULL_PPR":
        raise ValueError("Knockout V1 expects full-PPR scoring")
    if int(league.get("faab_start", 0)) != 1000:
        raise ValueError("Knockout V1 expects a $1,000 starting FAAB budget")
    if not bool(league.get("eliminated_roster_to_waivers", False)):
        raise ValueError("eliminated rosters must be released to waivers")

    week = int(state.get("current_week", 0))
    if week < 0 or week > 17:
        raise ValueError("current_week must be between 0 and 17")

    faab = int(state.get("faab_remaining", -1))
    if faab < 0 or faab > 1000:
        raise ValueError("faab_remaining must be between 0 and 1000")

    roster = list(state.get("roster") or [])
    status = str(state.get("status", "PRE_DRAFT"))
    if roster:
        validate_roster(roster, roster_size=int(league.get("roster_size", 14)))
    elif status not in {"PRE_DRAFT", "AWAITING_ROSTER"}:
        raise ValueError("active Knockout state requires a roster")

    eliminations = list(state.get("eliminations") or [])
    if len(eliminations) > 17:
        raise ValueError("there can be at most 17 eliminated teams")

    released_rosters = list(state.get("released_rosters") or [])
    seen_release_weeks: set[int] = set()
    elimination_keys = {
        (
            int(row.get("week", -1)),
            str(row.get("team") or "").strip().casefold(),
        )
        for row in eliminations
    }
    for released in released_rosters:
        release_week = int(released.get("week", -1))
        release_team = str(released.get("team") or "").strip()
        if release_week in seen_release_weeks:
            raise ValueError(f"duplicate released roster for Week {release_week}")
        if (release_week, release_team.casefold()) not in elimination_keys:
            raise ValueError("released roster does not match a recorded elimination")
        validate_roster(
            released.get("players") or [],
            roster_size=int(league.get("roster_size", 14)),
        )
        seen_release_weeks.add(release_week)
    return state


def phase(state: dict[str, Any]) -> str:
    status = str(state.get("status", "PRE_DRAFT"))
    week = int(state.get("current_week", 0))
    if status == "ELIMINATED":
        return "ELIMINATED"
    if status == "CHAMPION":
        return "CHAMPION"
    if week <= 0 or not state.get("roster"):
        return "PRE_DRAFT"
    if week <= 5:
        return "EARLY_SURVIVAL"
    if week <= 11:
        return "MIDSEASON"
    return "ENDGAME"


def active_team_count(state: dict[str, Any]) -> int:
    return max(1, int((state.get("league") or {}).get("teams", 18)) - len(state.get("eliminations") or []))


def strategy_priorities(state: dict[str, Any]) -> list[str]:
    current_phase = phase(state)
    faab = int(state.get("faab_remaining", 1000))
    if current_phase == "PRE_DRAFT":
        return [
            "Build a lineup with secure Week 1-4 roles and enough RB/WR depth to absorb one injury or miss.",
            "Avoid stacking too many starters on the same bye week; elimination risk matters more than theoretical season-long value.",
            "Draft for weekly floor first, then use eliminated-roster waivers to add ceiling as the field shrinks.",
            "Do not plan around trades: the current league rules do not allow them.",
        ]
    if current_phase == "EARLY_SURVIVAL":
        return [
            "Prioritize avoiding the weekly floor outcome over maximizing median season-long value.",
            "Spend FAAB when an eliminated roster materially raises this week's starting floor; replacement talent becomes scarcer after every elimination.",
            "Keep enough bench coverage for injuries and byes because trades are unavailable.",
            f"Current FAAB remaining: ${faab}.",
        ]
    if current_phase == "MIDSEASON":
        return [
            "Reprice the roster every week against the shrinking field; average strength rises as eliminated stars recycle through waivers.",
            "Use FAAB more aggressively on players who immediately enter the starting lineup.",
            "Bench depth still matters, but dead roster spots are increasingly expensive.",
            f"Current FAAB remaining: ${faab}.",
        ]
    if current_phase == "ENDGAME":
        return [
            "Optimize for winning the remaining weeks, not preserving theoretical long-term depth.",
            "Concentrate FAAB on direct starting-lineup upgrades and high-leverage injury replacements.",
            "Ceiling becomes more valuable as the field gets small, but a zero or unusable starter can still end the season immediately.",
            f"Current FAAB remaining: ${faab}.",
        ]
    return ["Season state is final; no further survival decisions are required."]


def roster_depth(state: dict[str, Any]) -> dict[str, Any]:
    roster = list(state.get("roster") or [])
    counts = {
        pos: sum(canonical_position(row.get("position")) == pos for row in roster)
        for pos in VALID_POSITIONS
    }
    required = dict(REQUIRED_STARTERS)
    cushions = {
        pos: counts[pos] - required[pos]
        for pos in REQUIRED_STARTERS
    }
    flex_count = sum(counts[pos] for pos in FLEX_POSITIONS)
    flex_cushion = flex_count - 6

    starter_gaps = [
        pos
        for pos, needed in required.items()
        if counts[pos] < needed
    ]
    thin_positions = [
        pos
        for pos, needed in required.items()
        if counts[pos] == needed
    ]
    if flex_cushion <= 0 and not any(pos in starter_gaps for pos in FLEX_POSITIONS):
        thin_positions.append("FLEX")

    return {
        "counts": counts,
        "required": required,
        "cushions": cushions,
        "flex_count": flex_count,
        "flex_cushion": flex_cushion,
        "starter_gaps": starter_gaps,
        "thin_positions": list(dict.fromkeys(thin_positions)),
    }


def structural_roster_risk(state: dict[str, Any]) -> dict[str, Any]:
    current_phase = phase(state)
    if current_phase == "PRE_DRAFT":
        return {
            "level": "NOT SCORED",
            "reason": "Roster risk begins after the draft roster is recorded.",
        }
    if current_phase in {"ELIMINATED", "CHAMPION"}:
        return {
            "level": "FINAL",
            "reason": "The Knockout season state is final.",
        }

    depth = roster_depth(state)
    if depth["starter_gaps"]:
        return {
            "level": "HIGH",
            "reason": (
                "Required starter coverage is missing at "
                + ", ".join(depth["starter_gaps"])
                + "."
            ),
        }

    thin = list(depth["thin_positions"])
    if len(thin) >= 3 or depth["flex_cushion"] <= 0:
        return {
            "level": "MEDIUM",
            "reason": (
                "The lineup is startable, but depth is thin at "
                + ", ".join(thin or ["FLEX"])
                + "."
            ),
        }

    return {
        "level": "LOW",
        "reason": "No required starter gap or broad skill-position depth warning is present.",
    }


def faab_posture(state: dict[str, Any]) -> dict[str, Any]:
    league = state.get("league") or {}
    start = max(1, int(league.get("faab_start", 1000)))
    remaining = int(state.get("faab_remaining", start))
    pct_remaining = remaining / start
    current_phase = phase(state)
    risk = structural_roster_risk(state)

    if current_phase == "PRE_DRAFT":
        posture = "HOLD"
        reason = "Do not spend FAAB before the draft roster exists."
    elif current_phase in {"ELIMINATED", "CHAMPION"}:
        posture = "FINAL"
        reason = "No further FAAB decisions are required."
    elif risk["level"] == "HIGH":
        posture = "URGENT"
        reason = "Starter coverage is incomplete; roster repair takes priority over budget preservation."
    elif current_phase == "ENDGAME":
        posture = "AGGRESSIVE"
        reason = "The field is small; direct starting-lineup upgrades matter more than preserving budget."
    elif current_phase == "MIDSEASON":
        posture = "ACTIVE"
        reason = "Use FAAB on players who immediately improve a starter or repair thin depth."
    else:
        posture = "SELECTIVE"
        reason = "Preserve flexibility early and spend when a move materially improves weekly survival structure."

    return {
        "posture": posture,
        "remaining": remaining,
        "start": start,
        "pct_remaining": pct_remaining,
        "reason": reason,
    }


def knockout_decision_summary(state: dict[str, Any]) -> dict[str, Any]:
    current_phase = phase(state)
    risk = structural_roster_risk(state)
    faab = faab_posture(state)
    readiness = draft_readiness(state)
    alive = active_team_count(state)

    if current_phase == "PRE_DRAFT":
        next_action = "DRAFT ROSTER"
        why = "No roster is recorded yet. Draft a startable 14-player roster before player-level survival decisions are scored."
    elif current_phase == "ELIMINATED":
        next_action = "SEASON COMPLETE"
        why = "Your team has been eliminated."
    elif current_phase == "CHAMPION":
        next_action = "SEASON COMPLETE"
        why = "The state is marked champion."
    elif not readiness["ready"]:
        next_action = "FIX STARTER COVERAGE"
        why = "; ".join(readiness["lineup_errors"]) or "The current roster cannot fill every required starter slot."
    else:
        latest_elimination = max(
            (int(row.get("week", 0)) for row in state.get("eliminations") or []),
            default=0,
        )
        released_weeks = {
            int(row.get("week", 0))
            for row in state.get("released_rosters") or []
        }
        if latest_elimination and latest_elimination not in released_weeks:
            next_action = "LOAD ELIMINATED ROSTER"
            why = "The latest eliminated team's players should be reviewed before the next waiver cycle."
        elif risk["level"] == "MEDIUM":
            next_action = "REVIEW THIN DEPTH"
            why = risk["reason"]
        else:
            next_action = "HOLD / SHOP"
            why = "The roster is structurally startable; avoid forcing moves that do not improve a starter or fragile depth."

    return {
        "phase": current_phase,
        "teams_alive": alive,
        "roster_risk": risk,
        "faab": faab,
        "next_action": next_action,
        "why": why,
    }


def _candidate_fit_level(state: dict[str, Any], position: str) -> tuple[str, str]:
    pos = canonical_position(position)
    depth = roster_depth(state)
    counts = depth["counts"]
    required = depth["required"]

    if pos in required and counts[pos] < required[pos]:
        return "URGENT", f"{pos} has an unfilled required starter slot."

    if pos in FLEX_POSITIONS:
        if counts[pos] <= required[pos]:
            return "HIGH", f"{pos} depth is at the starter minimum."
        if depth["flex_cushion"] <= 1:
            return "HIGH", "RB/WR/TE depth has little cushion beyond the FLEX requirement."
        return "DEPTH", f"{pos} is currently covered; candidate would be a depth option."

    if pos == "QB":
        if counts[pos] <= 1:
            return "MEDIUM", "Only one QB is rostered; candidate adds injury/bye coverage."
        return "DEPTH", "QB starter coverage is already backed up."

    if pos in {"K", "DST"}:
        if counts[pos] < 1:
            return "URGENT", f"{pos} starter coverage is missing."
        return "LOW", f"{pos} is already covered; quality evidence is required before spending a bench spot."

    return "DEPTH", "Candidate fit is structural only."


def released_roster_fit(state: dict[str, Any], released: dict[str, Any]) -> list[dict[str, Any]]:
    players = list(released.get("players") or [])
    rows: list[dict[str, Any]] = []
    for player in players:
        level, reason = _candidate_fit_level(state, str(player.get("position") or ""))
        rows.append(
            {
                "player": str(player.get("player") or "").strip(),
                "position": canonical_position(player.get("position")),
                "nfl_team": str(player.get("nfl_team") or "").strip().upper(),
                "fit": level,
                "why": reason,
            }
        )
    rows.sort(key=lambda row: (FIT_PRIORITY.get(str(row["fit"]), 99), row["position"], row["player"].casefold()))
    return rows


def record_released_roster(
    state: dict[str, Any],
    *,
    week: int,
    team: str,
    players: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    validate_state(state)
    week = int(week)
    team_name = str(team or "").strip()
    if not team_name:
        raise ValueError("eliminated team name is required")

    elimination_matches = [
        row
        for row in state.get("eliminations") or []
        if int(row.get("week", -1)) == week
        and str(row.get("team") or "").strip().casefold() == team_name.casefold()
    ]
    if len(elimination_matches) != 1:
        raise ValueError("released roster must match a recorded weekly elimination")

    if any(
        int(row.get("week", -1)) == week
        for row in state.get("released_rosters") or []
    ):
        raise ValueError(f"released roster for Week {week} is already recorded")

    league = state.get("league") or {}
    normalized = validate_roster(
        players,
        roster_size=int(league.get("roster_size", 14)),
    )
    updated = deepcopy(state)
    updated.setdefault("released_rosters", []).append(
        {
            "week": week,
            "team": team_name,
            "players": normalized,
        }
    )
    return updated


def draft_readiness(state: dict[str, Any]) -> dict[str, Any]:
    league = state.get("league") or {}
    roster = list(state.get("roster") or [])
    required_count = int(league.get("roster_size", 14))
    if not roster:
        return {
            "ready": False,
            "status": "AWAITING_DRAFT_ROSTER",
            "roster_count": 0,
            "required_roster_count": required_count,
            "lineup_errors": [],
        }
    validate_roster(roster, roster_size=required_count)
    lineup = lineup_readiness(roster)
    return {
        "ready": bool(lineup["ready"]),
        "status": (
            "READY_FOR_WEEK_1"
            if lineup["ready"] and int(state.get("current_week", 0)) <= 1
            else "ACTIVE"
            if lineup["ready"]
            else "ROSTER_LOADED_LINEUP_INCOMPLETE"
        ),
        "roster_count": len(roster),
        "required_roster_count": required_count,
        "lineup_errors": list(lineup["errors"]),
    }


def record_draft_state(state: dict[str, Any], roster: Iterable[dict[str, Any]]) -> dict[str, Any]:
    validate_state(state)
    updated = deepcopy(state)
    league = updated.get("league") or {}
    normalized = validate_roster(roster, roster_size=int(league.get("roster_size", 14)))
    if updated.get("roster"):
        raise ValueError("draft roster is already recorded")
    updated["roster"] = normalized
    updated["status"] = "ACTIVE"
    updated["current_week"] = 1
    return updated


def record_week_state(
    state: dict[str, Any],
    *,
    user_score: float,
    eliminated_team: str,
    user_eliminated: bool = False,
) -> dict[str, Any]:
    validate_state(state)
    updated = deepcopy(state)
    if phase(updated) in {"PRE_DRAFT", "ELIMINATED", "CHAMPION"}:
        raise ValueError("week result cannot be recorded in the current Knockout phase")

    week = int(updated["current_week"])
    if any(int(row.get("week", -1)) == week for row in updated.get("weekly_results") or []):
        raise ValueError(f"Week {week} is already recorded")
    eliminated_team = str(eliminated_team or "").strip()
    if not eliminated_team:
        raise ValueError("eliminated team name is required")

    updated.setdefault("weekly_results", []).append(
        {"week": week, "user_score": float(user_score), "user_eliminated": bool(user_eliminated)}
    )
    updated.setdefault("eliminations", []).append({"week": week, "team": eliminated_team})

    if user_eliminated:
        updated["status"] = "ELIMINATED"
        return updated
    if week >= 17:
        updated["status"] = "CHAMPION"
        return updated
    updated["current_week"] = week + 1
    return updated


def record_faab_spend(state: dict[str, Any], amount: int, *, note: str = "") -> dict[str, Any]:
    validate_state(state)
    amount = int(amount)
    if amount < 0:
        raise ValueError("FAAB spend cannot be negative")
    remaining = int(state.get("faab_remaining", 0))
    if amount > remaining:
        raise ValueError("FAAB spend exceeds remaining budget")
    updated = deepcopy(state)
    updated["faab_remaining"] = remaining - amount
    updated.setdefault("faab_transactions", []).append(
        {"week": int(updated.get("current_week", 0)), "amount": amount, "note": str(note or "").strip()}
    )
    return updated


def record_waiver_transaction(
    state: dict[str, Any],
    *,
    amount: int,
    add_player: dict[str, Any],
    drop_player: str,
    note: str = "",
) -> dict[str, Any]:
    """Record one completed add/drop and keep the live roster authoritative."""
    validate_state(state)
    if phase(state) in {"PRE_DRAFT", "ELIMINATED", "CHAMPION"}:
        raise ValueError("waiver transactions require an active Knockout roster")

    amount = int(amount)
    if amount < 0:
        raise ValueError("FAAB spend cannot be negative")
    remaining = int(state.get("faab_remaining", 0))
    if amount > remaining:
        raise ValueError("FAAB spend exceeds remaining budget")

    drop_name = str(drop_player or "").strip()
    if not drop_name:
        raise ValueError("drop player is required")

    roster = [dict(row) for row in state.get("roster") or []]
    matches = [i for i, row in enumerate(roster) if str(row.get("player", "")).casefold() == drop_name.casefold()]
    if len(matches) != 1:
        raise ValueError(f"drop player is not uniquely present on roster: {drop_name}")

    replacement = {
        "player": str(add_player.get("player", "")).strip(),
        "position": canonical_position(add_player.get("position")),
        "nfl_team": str(add_player.get("nfl_team", "")).strip().upper(),
    }
    roster[matches[0]] = replacement
    normalized = validate_roster(roster, roster_size=int((state.get("league") or {}).get("roster_size", 14)))

    updated = deepcopy(state)
    updated["roster"] = normalized
    updated["faab_remaining"] = remaining - amount
    updated.setdefault("faab_transactions", []).append(
        {
            "week": int(updated.get("current_week", 0)),
            "amount": amount,
            "add": replacement["player"],
            "drop": drop_name,
            "note": str(note or "").strip(),
        }
    )
    return updated
