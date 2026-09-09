from __future__ import annotations

from src.knockout import engine
from src.knockout.espn_sync import apply_espn_snapshot, disconnect_espn


def base_state() -> dict:
    return {
        "schema_version": "knockout_live_state_v1",
        "season": 2026,
        "status": "AWAITING_ROSTER",
        "current_week": 0,
        "faab_remaining": 1000,
        "roster": [],
        "weekly_results": [],
        "eliminations": [],
        "faab_transactions": [],
        "league": {
            "name": "Elwood TKO",
            "teams": 18,
            "scoring": "FULL_PPR",
            "roster_size": 14,
            "starters": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "K": 1, "DST": 1},
            "faab_start": 1000,
            "faab_type": "CONTINUOUS",
            "trades_allowed": False,
            "elimination_rule": "LOWEST_WEEKLY_SCORE",
            "elimination_weeks": "1-17",
            "eliminated_roster_to_waivers": True,
            "espn_league_id": "987654",
            "espn_team_id": 7,
        },
    }


def snapshot() -> dict:
    positions = [
        ("QB One", "QB", "DAL"),
        ("RB One", "RB", "LAC"),
        ("RB Two", "RB", "DEN"),
        ("RB Three", "RB", "WSH"),
        ("RB Four", "RB", "ARI"),
        ("RB Five", "RB", "KC"),
        ("RB Six", "RB", "SF"),
        ("WR One", "WR", "CIN"),
        ("WR Two", "WR", "CLE"),
        ("WR Three", "WR", "PHI"),
        ("WR Four", "WR", "NYJ"),
        ("TE One", "TE", "NYG"),
        ("K One", "K", "BAL"),
        ("DST One", "DST", "ATL"),
    ]
    return {
        "provider": "ESPN",
        "league_id": "987654",
        "league_name": "Elwood TKO",
        "season": 2026,
        "team_count": 18,
        "team_id": 7,
        "team_name": "Tuck Team",
        "current_week": 1,
        "faab_start": 1000,
        "faab_remaining": 875,
        "roster_size": 14,
        "current_score": 91.25,
        "roster": [
            {"player": player, "position": position, "nfl_team": team}
            for player, position, team in positions
        ],
    }


def test_apply_espn_snapshot_activates_and_syncs_authoritative_roster() -> None:
    updated = apply_espn_snapshot(
        base_state(),
        snapshot(),
        credential_envelope="encrypted-token",
        synced_at_utc="2026-09-09T14:00:00+00:00",
    )

    assert updated["status"] == "ACTIVE"
    assert updated["current_week"] == 1
    assert updated["faab_remaining"] == 875
    assert updated["league"]["name"] == "Elwood TKO"
    assert len(updated["roster"]) == 14
    assert engine.draft_readiness(updated)["ready"] is True
    assert updated["espn_connection"]["league_id"] == "987654"
    assert updated["espn_connection"]["source_current_score"] == 91.25
    assert "espn_s2" not in str(updated)


def test_resync_preserves_knockout_history_and_existing_envelope() -> None:
    active = apply_espn_snapshot(
        base_state(),
        snapshot(),
        credential_envelope="encrypted-token",
    )
    active["weekly_results"] = [{"week": 1, "user_score": 120.0, "user_eliminated": False}]
    active["eliminations"] = [{"week": 1, "team": "Other Team"}]
    active["current_week"] = 2

    new_snapshot = snapshot()
    new_snapshot["current_week"] = 2
    new_snapshot["faab_remaining"] = 700
    updated = apply_espn_snapshot(active, new_snapshot)

    assert updated["weekly_results"] == active["weekly_results"]
    assert updated["eliminations"] == active["eliminations"]
    assert updated["current_week"] == 2
    assert updated["faab_remaining"] == 700
    assert updated["espn_connection"]["credential_envelope"] == "encrypted-token"


def test_disconnect_removes_credentials_but_keeps_last_good_roster() -> None:
    connected = apply_espn_snapshot(
        base_state(),
        snapshot(),
        credential_envelope="encrypted-token",
    )
    disconnected = disconnect_espn(connected)

    assert "espn_connection" not in disconnected
    assert disconnected["roster"] == connected["roster"]
    assert disconnected["status"] == "ACTIVE"


def test_espn_identity_is_authoritative_not_optional_metadata() -> None:
    bad = snapshot()
    bad["team_id"] = 8

    try:
        apply_espn_snapshot(
            base_state(),
            bad,
            credential_envelope="encrypted-token",
        )
    except ValueError as exc:
        assert "configured for team 7" in str(exc)
    else:
        raise AssertionError("wrong ESPN team must be rejected")


def test_discovered_elwood_relink_updates_provider_ids() -> None:
    discovered = snapshot()
    discovered["league_id"] = "222222"
    discovered["team_id"] = 9
    discovered["league_name"] = "Elwood TKO"
    discovered["discovered_relink"] = True

    updated = apply_espn_snapshot(
        base_state(),
        discovered,
        credential_envelope="encrypted-token",
    )

    assert updated["league"]["espn_league_id"] == "222222"
    assert updated["league"]["espn_team_id"] == 9
    assert updated["espn_connection"]["league_id"] == "222222"
    assert len(updated["roster"]) == 14


def test_discovered_different_league_cannot_relink() -> None:
    discovered = snapshot()
    discovered["league_id"] = "222222"
    discovered["team_id"] = 9
    discovered["league_name"] = "Not Elwood TKO"
    discovered["discovered_relink"] = True

    try:
        apply_espn_snapshot(
            base_state(),
            discovered,
            credential_envelope="encrypted-token",
        )
    except ValueError as exc:
        assert "configured for league" in str(exc)
    else:
        raise AssertionError("different ESPN league name must not relink Knockout")


def test_espn_sync_preserves_lineup_details() -> None:
    snap = snapshot()
    snap["roster"][0]["lineup_role"] = "QB"
    snap["roster"][0]["lineup_slot_id"] = 0
    snap["roster"][0]["injury_status"] = "ACTIVE"

    updated = apply_espn_snapshot(
        base_state(),
        snap,
        credential_envelope="encrypted-token",
    )

    details = updated["espn_connection"]["roster_details"]
    assert len(details) == 14
    assert details[0]["lineup_role"] == "QB"
    assert details[0]["lineup_slot_id"] == 0
