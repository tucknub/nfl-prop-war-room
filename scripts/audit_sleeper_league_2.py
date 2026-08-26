from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

API_BASE = "https://api.sleeper.app/v1"


def fetch_json(path: str):
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        headers={"Accept": "application/json", "User-Agent": "PropWar-FantasyAudit/1.0"},
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> None:
    league_id = str(sys.argv[1])
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)

    league = fetch_json(f"/league/{league_id}")
    users = fetch_json(f"/league/{league_id}/users")
    rosters = fetch_json(f"/league/{league_id}/rosters")
    drafts = fetch_json(f"/league/{league_id}/drafts")

    write_json(out / "league.json", league)
    write_json(out / "users.json", users)
    write_json(out / "rosters.json", rosters)
    write_json(out / "drafts.json", drafts)

    previous = league.get("previous_league_id")
    previous_league = None
    if previous:
        previous_league = fetch_json(f"/league/{previous}")
        write_json(out / "previous_league.json", previous_league)

    roster_positions = list(league.get("roster_positions") or [])
    starters = [slot for slot in roster_positions if slot not in {"BN", "IR", "TAXI"}]
    scoring = dict(league.get("scoring_settings") or {})
    settings = dict(league.get("settings") or {})

    draft_summary = []
    for draft in drafts if isinstance(drafts, list) else []:
        dsettings = dict(draft.get("settings") or {})
        draft_summary.append({
            "draft_id": draft.get("draft_id"),
            "status": draft.get("status"),
            "type": draft.get("type"),
            "start_time": draft.get("start_time"),
            "rounds": dsettings.get("rounds"),
            "teams": dsettings.get("teams"),
            "slots_qb": dsettings.get("slots_qb"),
            "slots_rb": dsettings.get("slots_rb"),
            "slots_wr": dsettings.get("slots_wr"),
            "slots_te": dsettings.get("slots_te"),
            "slots_flex": dsettings.get("slots_flex"),
            "slots_super_flex": dsettings.get("slots_super_flex"),
            "slots_def": dsettings.get("slots_def"),
            "slots_k": dsettings.get("slots_k"),
            "slots_bn": dsettings.get("slots_bn"),
            "draft_order": draft.get("draft_order"),
        })

    nonempty_rosters = 0
    for roster in rosters if isinstance(rosters, list) else []:
        if roster.get("players"):
            nonempty_rosters += 1

    summary = {
        "league_id": league_id,
        "name": league.get("name"),
        "season": league.get("season"),
        "status": league.get("status"),
        "total_rosters": league.get("total_rosters"),
        "previous_league_id": previous,
        "previous_name": previous_league.get("name") if isinstance(previous_league, dict) else None,
        "previous_season": previous_league.get("season") if isinstance(previous_league, dict) else None,
        "manager_display_names": sorted(str(u.get("display_name") or u.get("username") or "") for u in users),
        "roster_positions": roster_positions,
        "starter_positions": starters,
        "bench_slots": roster_positions.count("BN"),
        "ir_slots": roster_positions.count("IR"),
        "taxi_slots": roster_positions.count("TAXI"),
        "qb_starter_slots": starters.count("QB"),
        "superflex_present": any(s in {"SUPER_FLEX", "OP"} for s in roster_positions),
        "ppr_points_per_reception": scoring.get("rec"),
        "pass_td_points": scoring.get("pass_td"),
        "pass_int_points": scoring.get("pass_int"),
        "rush_yd_points": scoring.get("rush_yd"),
        "rec_yd_points": scoring.get("rec_yd"),
        "rush_td_points": scoring.get("rush_td"),
        "rec_td_points": scoring.get("rec_td"),
        "waiver_budget": settings.get("waiver_budget"),
        "waiver_type": settings.get("waiver_type"),
        "max_keepers": settings.get("max_keepers"),
        "playoff_teams": settings.get("playoff_teams"),
        "playoff_week_start": settings.get("playoff_week_start"),
        "trade_deadline": settings.get("trade_deadline"),
        "reserve_slots": settings.get("reserve_slots"),
        "draft_rounds_league_field": settings.get("draft_rounds"),
        "user_count": len(users) if isinstance(users, list) else None,
        "roster_count": len(rosters) if isinstance(rosters, list) else None,
        "nonempty_roster_count": nonempty_rosters,
        "draft_count": len(drafts) if isinstance(drafts, list) else None,
        "drafts": draft_summary,
        "scoring_settings": scoring,
        "settings": settings,
    }

    write_json(out / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
