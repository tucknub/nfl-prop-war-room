from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

API_BASE = "https://api.sleeper.app/v1"


def fetch_json(path: str):
    url = f"{API_BASE}{path}"
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "PropWar-FantasyAudit/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} for {url}: {exc.read().decode('utf-8', errors='replace')[:500]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to fetch {url}: {exc}") from exc
    return json.loads(payload)


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: audit_sleeper_league.py LEAGUE_ID OUTPUT_DIR")

    league_id = str(sys.argv[1])
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)

    league = fetch_json(f"/league/{league_id}")
    if not isinstance(league, dict) or str(league.get("league_id", "")) != league_id:
        raise RuntimeError("Sleeper league response did not match requested league ID")

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
    scoring = dict(league.get("scoring_settings") or {})
    settings = dict(league.get("settings") or {})
    display_names = sorted(str(user.get("display_name") or user.get("username") or "") for user in users)

    starter_positions = [slot for slot in roster_positions if slot not in {"BN", "IR", "TAXI"}]
    summary = {
        "league_id": league_id,
        "name": league.get("name"),
        "season": league.get("season"),
        "status": league.get("status"),
        "total_rosters": league.get("total_rosters"),
        "previous_league_id": previous,
        "roster_positions": roster_positions,
        "starter_positions": starter_positions,
        "superflex_present": any(slot in {"SUPER_FLEX", "OP"} for slot in roster_positions),
        "qb_starter_slots": sum(1 for slot in starter_positions if slot == "QB"),
        "ppr_points_per_reception": scoring.get("rec"),
        "pass_td_points": scoring.get("pass_td"),
        "waiver_budget": settings.get("waiver_budget"),
        "max_keepers": settings.get("max_keepers"),
        "playoff_teams": settings.get("playoff_teams"),
        "trade_deadline": settings.get("trade_deadline"),
        "user_count": len(users) if isinstance(users, list) else None,
        "roster_count": len(rosters) if isinstance(rosters, list) else None,
        "draft_count": len(drafts) if isinstance(drafts, list) else None,
        "manager_display_names": display_names,
        "previous_season": previous_league.get("season") if isinstance(previous_league, dict) else None,
        "previous_name": previous_league.get("name") if isinstance(previous_league, dict) else None,
    }

    expected_managers = {
        "BigChuck87",
        "Tucknub",
        "hhEshhAy",
        "IllHelpYouGetYour50",
        "Going4Four",
        "BigSea",
        "alexclouse27",
        "tjwooderson",
        "xEDW4RDS",
        "rat46176",
    }
    summary["matches_2026_ffl_secondary_checkpoint"] = {
        "ten_teams": league.get("total_rosters") == 10,
        "full_ppr": scoring.get("rec") == 1,
        "one_qb": summary["qb_starter_slots"] == 1 and not summary["superflex_present"],
        "manager_set_matches": set(display_names) == expected_managers,
    }

    write_json(out / "summary.json", summary)

    checks = summary["matches_2026_ffl_secondary_checkpoint"]
    if not all(checks.values()):
        raise RuntimeError(f"Live Sleeper state disagrees with accepted FFL checkpoints: {checks}")

    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
