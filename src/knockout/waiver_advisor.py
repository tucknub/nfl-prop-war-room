from __future__ import annotations

from statistics import median
from typing import Any, Iterable, Mapping

from . import engine


_DECISION_ORDER = {"ADD": 0, "VALUE": 1, "PASS": 2}
_SERIOUS_STATUSES = {
    "IR",
    "INJURED RESERVE",
    "OUT",
    "SUSPENDED",
    "SUSPENSION",
    "PUP",
    "NFI",
}
_SKILL_POSITIONS = {"RB", "WR", "TE"}


def _number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _name_key(value: object) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _metric_map(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw in rows:
        name = str(raw.get("player") or "").strip()
        if name:
            result[_name_key(name)] = dict(raw)
    return result


def _roster_rows(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    connection = state.get("espn_connection") or {}
    metrics = _metric_map(connection.get("roster_player_metrics") or [])
    details = _metric_map(connection.get("roster_details") or [])
    rows: list[dict[str, Any]] = []
    for raw in state.get("roster") or []:
        name = str(raw.get("player") or "").strip()
        metric = metrics.get(_name_key(name), {})
        detail = details.get(_name_key(name), {})
        rows.append(
            {
                "player": name,
                "position": engine.canonical_position(raw.get("position")),
                "nfl_team": str(raw.get("nfl_team") or "").strip().upper(),
                "projected_points": _number(metric.get("projected_points")),
                "percent_owned": _number(metric.get("percent_owned")),
                "injury_status": str(
                    metric.get("injury_status")
                    or detail.get("injury_status")
                    or ""
                ).strip(),
                "lineup_role": str(detail.get("lineup_role") or "").strip(),
            }
        )
    return rows


def _available_rows(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    connection = state.get("espn_connection") or {}
    rostered = {_name_key(row.get("player")) for row in state.get("roster") or []}
    rows: list[dict[str, Any]] = []
    for raw in connection.get("available_players") or []:
        name = str(raw.get("player") or "").strip()
        position = engine.canonical_position(raw.get("position"))
        if (
            not name
            or _name_key(name) in rostered
            or position not in engine.VALID_POSITIONS
        ):
            continue
        rows.append(
            {
                "player": name,
                "position": position,
                "nfl_team": str(raw.get("nfl_team") or "").strip().upper(),
                "projected_points": _number(raw.get("projected_points")),
                "percent_owned": _number(raw.get("percent_owned")),
                "injury_status": str(raw.get("injury_status") or "").strip(),
            }
        )
    return rows


def _top(rows: Iterable[dict[str, Any]], position: str, count: int) -> list[dict[str, Any]]:
    eligible = [row for row in rows if row["position"] == position]
    eligible.sort(
        key=lambda row: (
            -(row["projected_points"] if row["projected_points"] is not None else 0.0),
            -(row["percent_owned"] if row["percent_owned"] is not None else 0.0),
            row["player"].casefold(),
        )
    )
    return eligible[:count]


def _optimize_lineup(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    fixed: list[tuple[str, dict[str, Any]]] = []
    for position, count in (("QB", 1), ("K", 1), ("DST", 1)):
        selected = _top(rows, position, count)
        if len(selected) < count:
            return None
        fixed.extend((position, row) for row in selected)

    skill = [row for row in rows if row["position"] in _SKILL_POSITIONS]
    best: dict[str, Any] | None = None
    for flex in skill:
        remaining = [row for row in skill if row["player"] != flex["player"]]
        rb = _top(remaining, "RB", 2)
        wr = _top(remaining, "WR", 2)
        te = _top(remaining, "TE", 1)
        if len(rb) < 2 or len(wr) < 2 or len(te) < 1:
            continue
        assignments = (
            fixed
            + [("RB", row) for row in rb]
            + [("WR", row) for row in wr]
            + [("TE", row) for row in te]
            + [("FLEX", flex)]
        )
        names = [row["player"] for _, row in assignments]
        if len(names) != len(set(names)):
            continue
        total = sum(
            row["projected_points"] if row["projected_points"] is not None else 0.0
            for _, row in assignments
        )
        candidate = {
            "total": float(total),
            "assignments": tuple(
                {
                    "slot": slot,
                    "player": row["player"],
                    "position": row["position"],
                    "projected_points": row["projected_points"],
                }
                for slot, row in assignments
            ),
            "starter_names": frozenset(names),
        }
        if best is None or candidate["total"] > best["total"]:
            best = candidate
    return best


def _latest_release_names(state: Mapping[str, Any]) -> set[str]:
    releases = list(state.get("released_rosters") or [])
    if not releases:
        return set()
    latest = max(releases, key=lambda row: int(row.get("week", 0)))
    return {_name_key(row.get("player")) for row in latest.get("players") or []}


def _phase_caps(state: Mapping[str, Any], decision: str) -> tuple[float, float]:
    current = engine.phase(dict(state))
    if current == "ENDGAME":
        return (55.0, 70.0) if decision == "ADD" else (35.0, 45.0)
    if current == "MIDSEASON":
        return (45.0, 55.0) if decision == "ADD" else (25.0, 35.0)
    return (30.0, 38.0) if decision == "ADD" else (15.0, 22.0)


def _bid_amounts(
    state: Mapping[str, Any],
    *,
    decision: str,
    lineup_delta: float,
    depth_delta: float | None,
    percent_owned: float | None,
) -> tuple[int, int]:
    if decision == "PASS":
        return 0, 0
    league = state.get("league") or {}
    start = max(1, int(league.get("faab_start") or 1000))
    remaining = max(0, int(state.get("faab_remaining") or 0))
    phase_multiplier = {
        "EARLY_SURVIVAL": 0.85,
        "MIDSEASON": 1.0,
        "ENDGAME": 1.18,
    }.get(engine.phase(dict(state)), 1.0)
    owned_bonus = 0.0
    if percent_owned is not None:
        owned_bonus = max(0.0, min(5.0, ((percent_owned - 80.0) / 20.0) * 5.0))
    impact = max(0.0, lineup_delta) * 3.0
    if lineup_delta < 0.5 and depth_delta is not None:
        impact += min(10.0, max(0.0, depth_delta)) * 0.7
    base_pct = (5.0 if decision == "ADD" else 2.0) + impact + owned_bonus
    target_cap, max_cap = _phase_caps(state, decision)
    target_pct = min(target_cap, max(1.0, base_pct * phase_multiplier))
    max_pct = min(max_cap, max(target_pct, target_pct * 1.28))

    def dollars(pct: float, *, odd_nudge: bool = False) -> int:
        raw = int(round(start * pct / 100.0))
        raw = max(1, raw)
        if odd_nudge and raw >= 5 and raw % 5 == 0:
            raw += 1
        return min(raw, remaining)

    return dollars(target_pct, odd_nudge=True), dollars(max_pct)


def _decision(
    *,
    status: str,
    lineup_delta: float,
    depth_delta: float | None,
    percent_owned: float | None,
) -> str:
    if status.strip().upper().replace("_", " ") in _SERIOUS_STATUSES:
        return "PASS"
    if lineup_delta >= 2.0:
        return "ADD"
    if lineup_delta >= 0.5:
        return "VALUE"
    if depth_delta is not None and depth_delta >= 4.0:
        return "VALUE"
    if (
        depth_delta is not None
        and depth_delta >= 2.0
        and percent_owned is not None
        and percent_owned >= 97.0
    ):
        return "VALUE"
    return "PASS"


def _candidate_row(
    state: Mapping[str, Any],
    candidate: dict[str, Any],
    current_rows: list[dict[str, Any]],
    baseline: dict[str, Any],
    release_names: set[str],
    projection_coverage: float,
) -> dict[str, Any]:
    candidate_projection = candidate.get("projected_points")
    baseline_starters = baseline["starter_names"]
    best: tuple[tuple[float, int, float, float, str], dict[str, Any], dict[str, Any]] | None = None

    for drop in current_rows:
        after_rows = [row for row in current_rows if row["player"] != drop["player"]]
        after_rows.append(candidate)
        after = _optimize_lineup(after_rows)
        if after is None:
            continue
        drop_projection = drop.get("projected_points")
        drop_owned = drop.get("percent_owned")
        tie_key = (
            float(after["total"]),
            1 if drop["player"] not in baseline_starters else 0,
            -(drop_owned if drop_owned is not None else 0.0),
            -(drop_projection if drop_projection is not None else 0.0),
            drop["player"].casefold(),
        )
        if best is None or tie_key > best[0]:
            best = (tie_key, drop, after)

    if best is None:
        return {
            **candidate,
            "decision": "PASS",
            "source": "CHOP" if _name_key(candidate["player"]) in release_names else "FA",
            "lineup_delta": 0.0,
            "depth_delta": None,
            "recommended_bid": 0,
            "max_bid": 0,
            "drop_player": "—",
            "target_slot": "—",
            "confidence": "LOW",
            "why": "No legal add/drop keeps the required lineup startable.",
        }

    _, drop, after = best
    lineup_delta = float(after["total"]) - float(baseline["total"])
    drop_projection = drop.get("projected_points")
    depth_delta = (
        float(candidate_projection) - float(drop_projection)
        if candidate_projection is not None and drop_projection is not None
        else None
    )
    decision = _decision(
        status=str(candidate.get("injury_status") or ""),
        lineup_delta=lineup_delta,
        depth_delta=depth_delta,
        percent_owned=candidate.get("percent_owned"),
    )
    recommended_bid, max_bid = _bid_amounts(
        state,
        decision=decision,
        lineup_delta=lineup_delta,
        depth_delta=depth_delta,
        percent_owned=candidate.get("percent_owned"),
    )
    target_assignment = next(
        (row for row in after["assignments"] if row["player"] == candidate["player"]),
        None,
    )
    target_slot = str((target_assignment or {}).get("slot") or candidate["position"])
    confidence = (
        "HIGH"
        if projection_coverage >= 0.85 and candidate_projection is not None
        else "MEDIUM"
        if projection_coverage >= 0.65 and candidate_projection is not None
        else "LOW"
    )

    why: list[str] = []
    if target_assignment is not None and lineup_delta >= 0.05:
        replaced = [
            row
            for row in baseline["assignments"]
            if row["slot"] == target_slot
            and row["player"] not in after["starter_names"]
        ]
        replacement = replaced[0]["player"] if replaced else "your current lineup"
        why.append(f"{target_slot} upgrade over {replacement}: {lineup_delta:+.1f} projected points.")
    elif depth_delta is not None and depth_delta >= 0.5:
        why.append(f"Depth upgrade over {drop['player']}: {depth_delta:+.1f} projected points.")
    else:
        why.append("Does not materially improve the current projected lineup.")
    if _name_key(candidate["player"]) in release_names:
        why.append("Newly available from the latest eliminated roster.")
    if decision != "PASS":
        why.append(
            "Hard max protects future FAAB."
            if engine.phase(dict(state)) == "EARLY_SURVIVAL"
            else "Max bid is capped by current field stage and remaining FAAB."
        )

    return {
        **candidate,
        "decision": decision,
        "source": "CHOP" if _name_key(candidate["player"]) in release_names else "FA",
        "lineup_delta": round(lineup_delta, 2),
        "depth_delta": round(depth_delta, 2) if depth_delta is not None else None,
        "recommended_bid": recommended_bid,
        "max_bid": max_bid,
        "drop_player": drop["player"] if decision != "PASS" else "—",
        "target_slot": target_slot if decision != "PASS" else "—",
        "confidence": confidence,
        "why": " ".join(why[:3]),
    }


def faab_context(state: Mapping[str, Any]) -> dict[str, Any]:
    connection = state.get("espn_connection") or {}
    rows = [dict(row) for row in connection.get("league_faab") or []]
    eliminated = {
        _name_key(row.get("team"))
        for row in state.get("eliminations") or []
        if str(row.get("team") or "").strip()
    }
    active = [row for row in rows if _name_key(row.get("team")) not in eliminated]
    mine_id = int(connection.get("team_id") or 0)
    mine = next((row for row in active if int(row.get("team_id") or 0) == mine_id), None)
    balances = [
        int(row["faab_remaining"])
        for row in active
        if row.get("faab_remaining") is not None
    ]
    if mine is None or not balances:
        return {
            "available": False,
            "rank": None,
            "team_count": len(active),
            "median": None,
            "mine": int(state.get("faab_remaining") or 0),
        }
    mine_balance = int(mine.get("faab_remaining") or 0)
    rank = 1 + sum(value > mine_balance for value in balances)
    return {
        "available": True,
        "rank": rank,
        "team_count": len(balances),
        "median": float(median(balances)),
        "mine": mine_balance,
    }


def build_claim_plan(board: Mapping[str, Any], *, limit: int = 5) -> list[dict[str, Any]]:
    candidates = [
        dict(row)
        for row in board.get("candidates") or []
        if row.get("decision") in {"ADD", "VALUE"}
    ]
    leaders: dict[str, str] = {}
    group_counts: dict[str, int] = {}
    plan: list[dict[str, Any]] = []
    for row in candidates:
        group = str(row.get("target_slot") or row.get("position") or "OTHER")
        if group_counts.get(group, 0) >= 2:
            continue
        leader = leaders.get(group)
        condition = "Submit" if leader is None else f"Only if {leader} is lost"
        if leader is None:
            leaders[group] = str(row["player"])
        group_counts[group] = group_counts.get(group, 0) + 1
        plan.append(
            {
                "priority": len(plan) + 1,
                "player": row["player"],
                "position": row["position"],
                "bid": row["recommended_bid"],
                "max_bid": row["max_bid"],
                "drop": row["drop_player"],
                "condition": condition,
            }
        )
        if len(plan) >= limit:
            break
    return plan


def build_waiver_war_room(state: Mapping[str, Any], *, limit: int = 20) -> dict[str, Any]:
    current_rows = _roster_rows(state)
    available = _available_rows(state)
    baseline = _optimize_lineup(current_rows)
    projected_count = sum(row.get("projected_points") is not None for row in current_rows)
    projection_coverage = projected_count / len(current_rows) if current_rows else 0.0

    if not current_rows or not available:
        return {
            "enabled": False,
            "reason": "ESPN roster or waiver-pool data is unavailable.",
            "projection_coverage": projection_coverage,
            "candidates": [],
            "claim_plan": [],
            "faab_context": faab_context(state),
        }
    if baseline is None:
        return {
            "enabled": False,
            "reason": "The synced roster cannot fill the required Knockout starting lineup.",
            "projection_coverage": projection_coverage,
            "candidates": [],
            "claim_plan": [],
            "faab_context": faab_context(state),
        }
    if projection_coverage < 0.5:
        return {
            "enabled": False,
            "reason": "Resync ESPN to load enough current roster projections for player-level waiver advice.",
            "projection_coverage": projection_coverage,
            "candidates": [],
            "claim_plan": [],
            "faab_context": faab_context(state),
        }

    release_names = _latest_release_names(state)
    ranked = [
        _candidate_row(
            state,
            candidate,
            current_rows,
            baseline,
            release_names,
            projection_coverage,
        )
        for candidate in available
    ]
    ranked.sort(
        key=lambda row: (
            _DECISION_ORDER.get(str(row.get("decision")), 9),
            -float(row.get("lineup_delta") or 0.0),
            -float(row.get("depth_delta") or 0.0),
            -float(row.get("percent_owned") or 0.0),
            str(row.get("player") or "").casefold(),
        )
    )
    ranked = ranked[: max(1, int(limit))]
    board = {
        "enabled": True,
        "reason": "",
        "projection_coverage": projection_coverage,
        "baseline_lineup_projection": round(float(baseline["total"]), 2),
        "candidates": ranked,
        "faab_context": faab_context(state),
    }
    board["claim_plan"] = build_claim_plan(board)
    return board


__all__ = [
    "build_claim_plan",
    "build_waiver_war_room",
    "faab_context",
]
