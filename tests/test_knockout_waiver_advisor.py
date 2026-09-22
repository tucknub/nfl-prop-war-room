from __future__ import annotations

from src.knockout import waiver_advisor
from src.knockout.espn_sync import apply_espn_snapshot


def _roster() -> list[dict[str, str]]:
    positions = ["QB", "QB", "RB", "RB", "RB", "RB", "WR", "WR", "WR", "WR", "TE", "TE", "K", "DST"]
    teams = ["IND", "BUF", "PHI", "DET", "KC", "SEA", "CIN", "MIN", "LA", "MIA", "SF", "ARI", "BAL", "PIT"]
    return [
        {"player": f"{position}{index}", "position": position, "nfl_team": team}
        for index, (position, team) in enumerate(zip(positions, teams), 1)
    ]


def _metrics() -> list[dict]:
    projections = [18, 14, 17, 11, 6, 5, 16, 14, 10, 8, 9, 5, 8, 7]
    rows = []
    for player, projection in zip(_roster(), projections):
        rows.append(
            {
                **player,
                "projected_points": projection,
                "percent_owned": 85.0,
                "injury_status": "ACTIVE",
            }
        )
    return rows


def _state() -> dict:
    roster = _roster()
    return {
        "schema_version": "knockout_live_state_v1",
        "season": 2026,
        "status": "ACTIVE",
        "current_week": 3,
        "faab_remaining": 780,
        "roster": roster,
        "weekly_results": [],
        "eliminations": [{"week": 2, "team": "Eliminated"}],
        "released_rosters": [
            {
                "week": 2,
                "team": "Eliminated",
                "players": [{"player": "Star RB", "position": "RB", "nfl_team": "DAL"}],
            }
        ],
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
        },
        "espn_connection": {
            "provider": "ESPN",
            "team_id": 7,
            "roster_details": roster,
            "roster_player_metrics": _metrics(),
            "available_players": [
                {"player": "Star RB", "position": "RB", "nfl_team": "DAL", "projected_points": 20.0, "percent_owned": 99.9, "injury_status": "ACTIVE"},
                {"player": "Backup RB", "position": "RB", "nfl_team": "TB", "projected_points": 18.0, "percent_owned": 98.0, "injury_status": "ACTIVE"},
                {"player": "Low WR", "position": "WR", "nfl_team": "NE", "projected_points": 3.0, "percent_owned": 10.0, "injury_status": "ACTIVE"},
                {"player": "Out RB", "position": "RB", "nfl_team": "NYJ", "projected_points": 30.0, "percent_owned": 99.0, "injury_status": "OUT"},
            ],
            "league_faab": [
                {"team_id": 7, "team": "Mine", "faab_remaining": 780},
                {"team_id": 2, "team": "Rich", "faab_remaining": 900},
                {"team_id": 3, "team": "Eliminated", "faab_remaining": 850},
                {"team_id": 4, "team": "Low", "faab_remaining": 500},
            ],
        },
    }


def test_war_room_promotes_real_lineup_upgrades_and_builds_fallbacks() -> None:
    board = waiver_advisor.build_waiver_war_room(_state())
    assert board["enabled"] is True
    assert board["projection_coverage"] == 1.0

    by_name = {row["player"]: row for row in board["candidates"]}
    star = by_name["Star RB"]
    backup = by_name["Backup RB"]
    assert star["decision"] == "ADD"
    assert star["source"] == "CHOP"
    assert star["lineup_delta"] > backup["lineup_delta"] > 0
    assert 0 < star["recommended_bid"] <= star["max_bid"] <= 780
    assert star["drop_player"] != "—"
    assert by_name["Low WR"]["decision"] == "PASS"
    assert by_name["Out RB"]["decision"] == "PASS"

    plan = board["claim_plan"]
    assert plan[0]["player"] == "Star RB"
    assert plan[0]["condition"] == "Submit"
    assert plan[1]["player"] == "Backup RB"
    assert "Star RB" in plan[1]["condition"]


def test_faab_context_ignores_eliminated_team() -> None:
    context = waiver_advisor.faab_context(_state())
    assert context["available"] is True
    assert context["team_count"] == 16
    assert context["rank"] == 2
    assert context["median"] == 780.0


def test_war_room_refuses_player_advice_when_roster_projection_coverage_is_too_low() -> None:
    state = _state()
    state["espn_connection"]["roster_player_metrics"] = _metrics()[:5]
    board = waiver_advisor.build_waiver_war_room(state)
    assert board["enabled"] is False
    assert "Resync ESPN" in board["reason"]


def test_espn_sync_persists_roster_metrics_and_full_league_faab() -> None:
    state = _state()
    state["eliminations"] = []
    state["released_rosters"] = []
    state["espn_connection"]["credential_envelope"] = "encrypted-token"
    snapshot = {
        "provider": "ESPN",
        "league_id": "60191612",
        "league_name": "Elwood TKO",
        "season": 2026,
        "team_count": 18,
        "team_id": 7,
        "team_name": "Mine",
        "current_week": 3,
        "faab_remaining": 780,
        "current_score": 0.0,
        "roster": _roster(),
        "roster_player_metrics": _metrics(),
        "league_faab": [{"team_id": 7, "team": "Mine", "faab_remaining": 780}],
        "team_roster_status": [
            {"team_id": 7, "team": "Mine", "roster_count": 14},
            {"team_id": 2, "team": "Chopped", "roster_count": 0},
        ],
        "available_players": [],
    }
    state["league"]["espn_league_id"] = "60191612"
    state["league"]["espn_team_id"] = 7
    updated = apply_espn_snapshot(state, snapshot)
    assert len(updated["espn_connection"]["roster_player_metrics"]) == 14
    assert updated["espn_connection"]["league_faab"][0]["faab_remaining"] == 780
    assert updated["espn_connection"]["team_roster_status"][1]["roster_count"] == 0


def test_backup_qb_with_zero_lineup_gain_does_not_receive_faab_bid() -> None:
    state = _state()
    state["espn_connection"]["available_players"].append(
        {
            "player": "Backup QB Upgrade",
            "position": "QB",
            "nfl_team": "DAL",
            "projected_points": 17.5,
            "percent_owned": 99.0,
            "injury_status": "ACTIVE",
        }
    )
    board = waiver_advisor.build_waiver_war_room(state)
    row = next(row for row in board["candidates"] if row["player"] == "Backup QB Upgrade")
    assert row["lineup_delta"] == 0.0
    assert row["decision"] == "PASS"
    assert row["recommended_bid"] == 0
    assert all(plan["player"] != "Backup QB Upgrade" for plan in board["claim_plan"])


def test_small_dst_edge_is_pass_but_skill_position_depth_can_still_be_value() -> None:
    state = _state()
    state["espn_connection"]["available_players"].extend(
        [
            {
                "player": "Slight DST",
                "position": "DST",
                "nfl_team": "DAL",
                "projected_points": 7.6,
                "percent_owned": 95.0,
                "injury_status": "ACTIVE",
            },
            {
                "player": "Depth TE",
                "position": "TE",
                "nfl_team": "NE",
                "projected_points": 8.0,
                "percent_owned": 99.0,
                "injury_status": "ACTIVE",
            },
        ]
    )
    board = waiver_advisor.build_waiver_war_room(state)
    by_name = {row["player"]: row for row in board["candidates"]}
    assert by_name["Slight DST"]["decision"] == "PASS"
    assert by_name["Slight DST"]["recommended_bid"] == 0
    assert by_name["Depth TE"]["decision"] == "VALUE"
    assert by_name["Depth TE"]["depth_delta"] == 3.0


def test_claim_plan_chains_claims_that_share_the_same_drop() -> None:
    board = {
        "candidates": [
            {"decision": "ADD", "player": "A", "position": "RB", "target_slot": "RB", "recommended_bid": 100, "max_bid": 130, "drop_player": "Bench X"},
            {"decision": "VALUE", "player": "B", "position": "RB", "target_slot": "RB", "recommended_bid": 80, "max_bid": 100, "drop_player": "Bench X"},
            {"decision": "VALUE", "player": "C", "position": "WR", "target_slot": "WR", "recommended_bid": 60, "max_bid": 80, "drop_player": "Bench X"},
        ]
    }
    plan = waiver_advisor.build_claim_plan(board)
    assert plan[0]["condition"] == "Submit"
    assert plan[1]["condition"] == "Only if A is lost"
    assert plan[2]["condition"] == "Only if A and B are lost"
