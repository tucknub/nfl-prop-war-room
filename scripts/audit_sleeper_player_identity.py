from __future__ import annotations

import csv
import json
import re
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

API_BASE = "https://api.sleeper.app/v1"
HISTORICAL_LEAGUES = {
    "ffl_2024": "1112703068749058048",
    "ffl_2025": "1242463021108838400",
    "papa_2024": "1041254319653720064",
    "papa_2025": "1237498478561603584",
}
PLAYER_POSITIONS = {"QB", "RB", "WR", "TE", "K"}

TEAM_VARIANTS = {
    "ARZ": "ARI", "ARI": "ARI", "BAL": "BAL", "BUF": "BUF", "CAR": "CAR", "CHI": "CHI",
    "CIN": "CIN", "CLE": "CLE", "DAL": "DAL", "DEN": "DEN", "DET": "DET", "GB": "GB",
    "GNB": "GB", "HOU": "HOU", "IND": "IND", "JAC": "JAX", "JAX": "JAX", "KC": "KC",
    "KAN": "KC", "LAC": "LAC", "LAR": "LAR", "LV": "LV", "LVR": "LV", "MIA": "MIA",
    "MIN": "MIN", "NE": "NE", "NEP": "NE", "NO": "NO", "NOR": "NO", "NYG": "NYG",
    "NYJ": "NYJ", "PHI": "PHI", "PIT": "PIT", "SEA": "SEA", "SF": "SF", "SFO": "SF",
    "TB": "TB", "TAM": "TB", "TEN": "TEN", "WAS": "WAS", "WSH": "WAS",
}


def fetch_json(path: str):
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        headers={"Accept": "application/json", "User-Agent": "PropWar-IdentityAudit/1.0"},
    )
    with urllib.request.urlopen(req, timeout=35) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    time.sleep(0.03)
    return payload


def normalize_name(value) -> str:
    text = "" if value is None else str(value).lower()
    text = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def canonical_team(value) -> str:
    text = "" if value is None else str(value).upper().strip()
    return TEAM_VARIANTS.get(text, text)


def load_propwar_crosswalk(path: Path):
    gsis_ids = set()
    by_name_team_pos = defaultdict(list)
    by_name_pos = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            pid = str(row.get("player_id") or "").strip()
            name = str(row.get("normalized_player_name") or normalize_name(row.get("player_name"))).strip()
            team = canonical_team(row.get("team"))
            pos = str(row.get("position") or "").upper().strip()
            if pid:
                gsis_ids.add(pid)
            if name:
                by_name_team_pos[(name, team, pos)].append(row)
                by_name_pos[(name, pos)].append(row)
    return gsis_ids, by_name_team_pos, by_name_pos


def historical_player_ids():
    ids = set()
    sources = defaultdict(set)
    for label, league_id in HISTORICAL_LEAGUES.items():
        rosters = fetch_json(f"/league/{league_id}/rosters") or []
        for roster in rosters:
            for pid in roster.get("players") or []:
                ids.add(str(pid)); sources[str(pid)].add(f"{label}:roster")
            for pid in roster.get("reserve") or []:
                ids.add(str(pid)); sources[str(pid)].add(f"{label}:reserve")
        drafts = fetch_json(f"/league/{league_id}/drafts") or []
        for draft in drafts:
            for pick in fetch_json(f"/draft/{draft['draft_id']}/picks") or []:
                pid = pick.get("player_id")
                if pid is not None:
                    ids.add(str(pid)); sources[str(pid)].add(f"{label}:draft")
    return ids, sources


def resolve_one(sleeper_id, player, gsis_ids, by_name_team_pos, by_name_pos):
    position = str(player.get("position") or "").upper().strip()
    team = canonical_team(player.get("team"))
    name = str(player.get("full_name") or player.get("first_name") or "").strip()
    norm = normalize_name(name)
    gsis = str(player.get("gsis_id") or "").strip()

    if position == "DEF":
        return "TEAM_DEFENSE", team or sleeper_id, None
    if gsis and gsis in gsis_ids:
        return "GSIS_DIRECT", gsis, None
    if gsis:
        # GSIS itself is authoritative identity evidence even if the committed crosswalk export predates this player.
        return "GSIS_EXTENSION_REQUIRED", gsis, None

    exact = by_name_team_pos.get((norm, team, position), [])
    exact_ids = sorted({str(r.get("player_id") or "") for r in exact if r.get("player_id")})
    if len(exact_ids) == 1:
        return "NAME_TEAM_POSITION_UNIQUE", exact_ids[0], None
    if len(exact_ids) > 1:
        return "AMBIGUOUS", None, f"{len(exact_ids)} exact candidates"

    loose = by_name_pos.get((norm, position), [])
    loose_ids = sorted({str(r.get("player_id") or "") for r in loose if r.get("player_id")})
    if len(loose_ids) == 1:
        return "NAME_POSITION_UNIQUE", loose_ids[0], None
    if len(loose_ids) > 1:
        return "AMBIGUOUS", None, f"{len(loose_ids)} name/position candidates"
    return "UNRESOLVED", None, None


def summarize_set(label, sleeper_ids, players, indexes):
    gsis_ids, by_name_team_pos, by_name_pos = indexes
    rows = []
    counts = Counter()
    ext_presence = Counter()
    yahoo_seen = defaultdict(list)
    for sid in sorted(sleeper_ids):
        p = players.get(str(sid))
        if not isinstance(p, dict):
            rows.append({"sleeper_player_id": sid, "status": "SLEEPER_PLAYER_MISSING"})
            counts["SLEEPER_PLAYER_MISSING"] += 1
            continue
        status, propwar_candidate, note = resolve_one(sid, p, gsis_ids, by_name_team_pos, by_name_pos)
        counts[status] += 1
        for key in ["gsis_id", "yahoo_id", "sportradar_id", "fantasy_data_id", "espn_id"]:
            if p.get(key) not in (None, ""):
                ext_presence[key] += 1
        if p.get("yahoo_id") not in (None, ""):
            yahoo_seen[str(p.get("yahoo_id"))].append(str(sid))
        rows.append({
            "sleeper_player_id": str(sid),
            "player_name": p.get("full_name"),
            "team": p.get("team"),
            "position": p.get("position"),
            "active": p.get("active"),
            "years_exp": p.get("years_exp"),
            "gsis_id": p.get("gsis_id"),
            "yahoo_id": p.get("yahoo_id"),
            "sportradar_id": p.get("sportradar_id"),
            "fantasy_data_id": p.get("fantasy_data_id"),
            "espn_id": p.get("espn_id"),
            "status": status,
            "propwar_candidate_id": propwar_candidate,
            "note": note,
        })
    total = len(rows)
    directish = sum(counts[k] for k in ["GSIS_DIRECT", "TEAM_DEFENSE"])
    canonicalizable = directish + counts["GSIS_EXTENSION_REQUIRED"] + counts["NAME_TEAM_POSITION_UNIQUE"] + counts["NAME_POSITION_UNIQUE"]
    return {
        "label": label,
        "total": total,
        "status_counts": dict(counts),
        "existing_crosswalk_or_team_defense_pct": round(100 * directish / total, 2) if total else None,
        "canonicalizable_with_extensions_pct": round(100 * canonicalizable / total, 2) if total else None,
        "external_id_presence": dict(ext_presence),
        "duplicate_yahoo_id_count": sum(1 for ids in yahoo_seen.values() if len(ids) > 1),
    }, rows


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: audit_sleeper_player_identity.py OUTPUT_DIR")
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    crosswalk = Path("outputs/identity/player_identity_crosswalk.csv")
    if not crosswalk.exists():
        raise RuntimeError("PropWar identity crosswalk not found")
    indexes = load_propwar_crosswalk(crosswalk)

    players = fetch_json("/players/nfl") or {}
    if not isinstance(players, dict) or not players:
        raise RuntimeError("Sleeper player map missing")

    historical_ids, sources = historical_player_ids()
    active_ids = {
        str(sid) for sid, p in players.items()
        if isinstance(p, dict)
        and p.get("active") is True
        and str(p.get("position") or "").upper() in (PLAYER_POSITIONS | {"DEF"})
    }
    active_skill_ids = {
        sid for sid in active_ids
        if str((players.get(sid) or {}).get("position") or "").upper() in PLAYER_POSITIONS
    }
    active_rookie_ids = {
        sid for sid in active_skill_ids
        if (players.get(sid) or {}).get("years_exp") in (0, "0")
    }

    summary = {}
    all_rows = {}
    for label, ids in [
        ("historical_real_league_players", historical_ids),
        ("current_active_player_pool", active_ids),
        ("current_active_skill_players", active_skill_ids),
        ("current_active_rookies", active_rookie_ids),
    ]:
        s, rows = summarize_set(label, ids, players, indexes)
        summary[label] = s
        all_rows[label] = rows

    # Attach historical provenance only to the historical detail file.
    for row in all_rows["historical_real_league_players"]:
        row["historical_sources"] = sorted(sources.get(row["sleeper_player_id"], []))

    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    (out / "historical_identity_rows.json").write_text(json.dumps(all_rows["historical_real_league_players"], indent=2, sort_keys=True), encoding="utf-8")
    (out / "current_active_identity_rows.json").write_text(json.dumps(all_rows["current_active_player_pool"], indent=2, sort_keys=True), encoding="utf-8")
    (out / "current_rookie_identity_rows.json").write_text(json.dumps(all_rows["current_active_rookies"], indent=2, sort_keys=True), encoding="utf-8")

    problem_rows = []
    for label, rows in all_rows.items():
        for row in rows:
            if row.get("status") in {"GSIS_EXTENSION_REQUIRED", "NAME_TEAM_POSITION_UNIQUE", "NAME_POSITION_UNIQUE", "AMBIGUOUS", "UNRESOLVED", "SLEEPER_PLAYER_MISSING"}:
                problem_rows.append({"set": label, **row})
    (out / "identity_extension_review.json").write_text(json.dumps(problem_rows, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps(summary, indent=2, sort_keys=True))
    print("\nIdentity extension/review rows:", len(problem_rows))


if __name__ == "__main__":
    main()
