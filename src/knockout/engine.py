from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable


VALID_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DST"}
FLEX_POSITIONS = {"RB", "WR", "TE"}
REQUIRED_STARTERS = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DST": 1}


def canonical_position(value: object) -> str:
    text = str(value or "").strip().upper().replace("D/ST", "DST").replace("DEF", "DST")
    return text


def validate_roster(roster: Iterable[dict[str, Any]], *, roster_size: int = 14) -> list[dict[str, str]]:
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

    counts = {pos: sum(row["position"] == pos for row in rows) for pos in VALID_POSITIONS}
    for pos, required in REQUIRED_STARTERS.items():
        if counts[pos] < required:
            raise ValueError(f"roster cannot fill required starters: need {required} {pos}, found {counts[pos]}")
    flex_pool = sum(counts[pos] for pos in FLEX_POSITIONS)
    if flex_pool < 6:  # 2 RB + 2 WR + 1 TE + 1 FLEX
        raise ValueError("roster cannot fill RB/WR/TE starters plus FLEX")
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


def draft_readiness(state: dict[str, Any]) -> dict[str, Any]:
    league = state.get("league") or {}
    roster = list(state.get("roster") or [])
    if not roster:
        return {
            "ready": False,
            "status": "AWAITING_DRAFT_ROSTER",
            "roster_count": 0,
            "required_roster_count": int(league.get("roster_size", 14)),
        }
    validate_roster(roster, roster_size=int(league.get("roster_size", 14)))
    return {
        "ready": True,
        "status": "READY_FOR_WEEK_1" if int(state.get("current_week", 0)) <= 1 else "ACTIVE",
        "roster_count": len(roster),
        "required_roster_count": int(league.get("roster_size", 14)),
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
