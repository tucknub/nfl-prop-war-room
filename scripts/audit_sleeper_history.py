from __future__ import annotations

import json
import statistics
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path

API_BASE = "https://api.sleeper.app/v1"
CURRENT_LEAGUES = {
    "franchise_football_league": "1383849993151987712",
    "papa_johns": "1356381517693079553",
}
OWNER_DISPLAY = "Tucknub"
MAX_SEASONS = 3


def fetch_json(path: str):
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "PropWar-HistoryAudit/1.0"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    time.sleep(0.03)
    return payload


def completed_transactions(league_id: str):
    out = []
    for week in range(1, 19):
        rows = fetch_json(f"/league/{league_id}/transactions/{week}") or []
        for row in rows:
            if row.get("status") == "complete":
                copy = dict(row)
                copy["_week"] = week
                out.append(copy)
    return out


def matchups(league_id: str):
    return {str(week): fetch_json(f"/league/{league_id}/matchups/{week}") or [] for week in range(1, 19)}


def draft_rows(league_id: str):
    drafts = fetch_json(f"/league/{league_id}/drafts") or []
    enriched = []
    for draft in drafts:
        d = dict(draft)
        d["picks"] = fetch_json(f"/draft/{draft['draft_id']}/picks") or []
        enriched.append(d)
    return enriched


def owner_user(users):
    for user in users:
        if str(user.get("display_name") or "").lower() == OWNER_DISPLAY.lower() or str(user.get("username") or "").lower() == OWNER_DISPLAY.lower():
            return user
    return None


def roster_for_owner(rosters, user_id):
    if user_id is None:
        return None
    for roster in rosters:
        if str(roster.get("owner_id")) == str(user_id):
            return roster
    return None


def summarize_transactions(transactions, owner_roster_id):
    types = Counter(str(t.get("type") or "unknown") for t in transactions)
    waiver_bids = []
    owner_waiver_bids = []
    owner_transaction_count = 0
    for t in transactions:
        rid_list = [str(v) for v in (t.get("roster_ids") or [])]
        if owner_roster_id is not None and str(owner_roster_id) in rid_list:
            owner_transaction_count += 1
        if t.get("type") == "waiver":
            bid = (t.get("settings") or {}).get("waiver_bid")
            if isinstance(bid, (int, float)):
                waiver_bids.append(float(bid))
                if owner_roster_id is not None and str(owner_roster_id) in rid_list:
                    owner_waiver_bids.append(float(bid))
    def stats(vals):
        if not vals:
            return {"count": 0, "median": None, "mean": None, "max": None}
        return {
            "count": len(vals),
            "median": statistics.median(vals),
            "mean": round(statistics.mean(vals), 2),
            "max": max(vals),
        }
    return {
        "completed_transaction_count": len(transactions),
        "types": dict(types),
        "completed_waiver_bid_stats": stats(waiver_bids),
        "owner_completed_waiver_bid_stats": stats(owner_waiver_bids),
        "owner_completed_transaction_count": owner_transaction_count,
    }


def summarize_drafts(drafts, owner_user_id, owner_roster_id):
    rows = []
    for d in drafts:
        owner_picks = []
        for p in d.get("picks") or []:
            if (owner_user_id and str(p.get("picked_by")) == str(owner_user_id)) or (owner_roster_id is not None and str(p.get("roster_id")) == str(owner_roster_id)):
                owner_picks.append({
                    "round": p.get("round"),
                    "pick_no": p.get("pick_no"),
                    "draft_slot": p.get("draft_slot"),
                    "player_id": p.get("player_id"),
                    "metadata": p.get("metadata"),
                })
        rows.append({
            "draft_id": d.get("draft_id"),
            "status": d.get("status"),
            "type": d.get("type"),
            "rounds": (d.get("settings") or {}).get("rounds"),
            "teams": (d.get("settings") or {}).get("teams"),
            "owner_pick_count": len(owner_picks),
            "owner_draft_slot": owner_picks[0].get("draft_slot") if owner_picks else None,
            "owner_picks": owner_picks,
        })
    return rows


def audit_family(name: str, current_league_id: str, out: Path):
    family_dir = out / name
    family_dir.mkdir(parents=True, exist_ok=True)
    seasons = []
    current = current_league_id
    previous_manager_ids = None
    for _ in range(MAX_SEASONS):
        if not current:
            break
        league = fetch_json(f"/league/{current}")
        users = fetch_json(f"/league/{current}/users") or []
        rosters = fetch_json(f"/league/{current}/rosters") or []
        transactions = completed_transactions(current)
        weekly_matchups = matchups(current)
        drafts = draft_rows(current)

        owner = owner_user(users)
        owner_id = owner.get("user_id") if owner else None
        owner_roster = roster_for_owner(rosters, owner_id)
        owner_roster_id = owner_roster.get("roster_id") if owner_roster else None
        manager_ids = {str(u.get("user_id")) for u in users if u.get("user_id") is not None}
        continuity = None if previous_manager_ids is None else len(manager_ids & previous_manager_ids)

        season_dir = family_dir / str(league.get("season"))
        season_dir.mkdir(parents=True, exist_ok=True)
        for filename, payload in {
            "league.json": league,
            "users.json": users,
            "rosters.json": rosters,
            "transactions.json": transactions,
            "matchups.json": weekly_matchups,
            "drafts.json": drafts,
        }.items():
            (season_dir / filename).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

        settings = league.get("settings") or {}
        scoring = league.get("scoring_settings") or {}
        owner_settings = (owner_roster or {}).get("settings") or {}
        season_summary = {
            "season": league.get("season"),
            "league_id": str(league.get("league_id")),
            "name": league.get("name"),
            "status": league.get("status"),
            "previous_league_id": league.get("previous_league_id"),
            "team_count": league.get("total_rosters"),
            "manager_count": len(users),
            "manager_continuity_from_newer_season": continuity,
            "roster_positions": league.get("roster_positions"),
            "ppr": scoring.get("rec"),
            "pass_td": scoring.get("pass_td"),
            "pass_int": scoring.get("pass_int"),
            "waiver_budget": settings.get("waiver_budget"),
            "max_keepers": settings.get("max_keepers"),
            "owner_present": owner is not None,
            "owner_roster_id": owner_roster_id,
            "owner_record": {
                "wins": owner_settings.get("wins"),
                "losses": owner_settings.get("losses"),
                "ties": owner_settings.get("ties"),
                "fpts": owner_settings.get("fpts"),
                "fpts_decimal": owner_settings.get("fpts_decimal"),
                "waiver_budget_used": owner_settings.get("waiver_budget_used"),
                "total_moves": owner_settings.get("total_moves"),
            },
            "transactions": summarize_transactions(transactions, owner_roster_id),
            "drafts": summarize_drafts(drafts, owner_id, owner_roster_id),
            "weeks_with_matchup_rows": sum(1 for rows in weekly_matchups.values() if rows),
        }
        seasons.append(season_summary)
        previous_manager_ids = manager_ids
        current = league.get("previous_league_id")

    return {"league_family": name, "seasons": seasons}


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: audit_sleeper_history.py OUTPUT_DIR")
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    summary = {name: audit_family(name, league_id, out) for name, league_id in CURRENT_LEAGUES.items()}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    # Print only compact, non-sensitive league/history statistics.
    compact = {}
    for family, payload in summary.items():
        compact[family] = []
        for s in payload["seasons"]:
            compact[family].append({
                "season": s["season"],
                "league_id": s["league_id"],
                "name": s["name"],
                "team_count": s["team_count"],
                "manager_count": s["manager_count"],
                "manager_continuity_from_newer_season": s["manager_continuity_from_newer_season"],
                "owner_present": s["owner_present"],
                "owner_roster_id": s["owner_roster_id"],
                "owner_record": s["owner_record"],
                "transactions": s["transactions"],
                "drafts": [{k: d[k] for k in ["status", "type", "rounds", "teams", "owner_pick_count", "owner_draft_slot"]} for d in s["drafts"]],
                "weeks_with_matchup_rows": s["weeks_with_matchup_rows"],
            })
    print(json.dumps(compact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
