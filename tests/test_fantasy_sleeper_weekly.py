from __future__ import annotations

import httpx
import pytest

from src.fantasy.sleeper import (
    SleeperClient,
    normalize_sleeper_draft_picks,
    normalize_sleeper_matchups,
    normalize_sleeper_transactions,
)


def test_matchups_preserve_platform_ids_order_and_score_evidence():
    rows = normalize_sleeper_matchups(
        [
            {
                "roster_id": 1,
                "matchup_id": 7,
                "players": ["101", "202", "IND"],
                "starters": ["202", "IND"],
                "points": 123.45,
                "custom_points": 120,
                "players_points": {"101": 4.0, "202": 15.5, "IND": 8.0},
                "starters_points": [15.5, 8.0],
            }
        ],
        week=4,
    )

    assert len(rows) == 1
    matchup = rows[0]
    assert matchup.week == 4
    assert matchup.platform_roster_id == "1"
    assert matchup.matchup_id == "7"
    assert matchup.players == ("101", "202", "IND")
    assert matchup.starters == ("202", "IND")
    assert matchup.points == 123.45
    assert matchup.custom_points == 120
    assert matchup.players_points["202"] == 15.5
    assert matchup.starters_points == (15.5, 8.0)


def test_matchups_keep_unpaired_or_unscored_provider_rows_without_inventing_values():
    rows = normalize_sleeper_matchups(
        [{"roster_id": 3, "matchup_id": None, "players": None, "starters": None, "points": None}],
        week=1,
    )

    assert rows[0].platform_roster_id == "3"
    assert rows[0].matchup_id is None
    assert rows[0].players == ()
    assert rows[0].starters == ()
    assert rows[0].points is None
    assert rows[0].custom_points is None


def test_transactions_preserve_add_drop_faab_and_pick_ownership_facts():
    rows = normalize_sleeper_transactions(
        [
            {
                "type": "waiver",
                "transaction_id": "tx-1",
                "status_updated": 1780000000200,
                "status": "complete",
                "settings": {"waiver_bid": 27},
                "roster_ids": [2],
                "metadata": {"notes": "processed"},
                "leg": 3,
                "drops": {"111": 2},
                "draft_picks": [
                    {
                        "season": "2027",
                        "round": 4,
                        "roster_id": 2,
                        "previous_owner_id": 2,
                        "owner_id": 5,
                    }
                ],
                "creator": "user-2",
                "created": 1780000000000,
                "consenter_ids": [2],
                "adds": {"222": 2},
                "waiver_budget": [{"sender": 2, "receiver": 5, "amount": 11}],
            }
        ]
    )

    assert len(rows) == 1
    transaction = rows[0]
    assert transaction.platform_transaction_id == "tx-1"
    assert transaction.transaction_type == "waiver"
    assert transaction.status == "complete"
    assert transaction.week == 3
    assert transaction.roster_ids == ("2",)
    assert transaction.creator_user_id == "user-2"
    assert transaction.consenter_roster_ids == ("2",)
    assert transaction.adds == {"222": "2"}
    assert transaction.drops == {"111": "2"}
    assert transaction.waiver_bid == 27
    assert transaction.metadata == {"notes": "processed"}
    assert transaction.traded_picks[0].season == "2027"
    assert transaction.traded_picks[0].original_roster_id == "2"
    assert transaction.traded_picks[0].owner_roster_id == "5"
    assert transaction.faab_transfers[0].sender_roster_id == "2"
    assert transaction.faab_transfers[0].receiver_roster_id == "5"
    assert transaction.faab_transfers[0].amount == 11


def test_transaction_null_provider_fields_normalize_to_empty_not_fake_events():
    rows = normalize_sleeper_transactions(
        [
            {
                "transaction_id": "tx-2",
                "type": "free_agent",
                "status": "complete",
                "leg": 1,
                "adds": None,
                "drops": None,
                "draft_picks": None,
                "waiver_budget": None,
                "settings": None,
                "metadata": None,
            }
        ]
    )

    transaction = rows[0]
    assert transaction.adds == {}
    assert transaction.drops == {}
    assert transaction.traded_picks == ()
    assert transaction.faab_transfers == ()
    assert transaction.waiver_bid is None
    assert transaction.metadata == {}


def test_draft_picks_preserve_player_roster_user_keeper_and_board_position():
    rows = normalize_sleeper_draft_picks(
        [
            {
                "player_id": "9999",
                "picked_by": "user-8",
                "roster_id": 8,
                "round": 2,
                "draft_slot": 5,
                "pick_no": 16,
                "metadata": {"position": "WR", "team": "IND"},
                "is_keeper": True,
                "draft_id": "draft-2026",
            },
            {
                "player_id": "IND",
                "picked_by": "",
                "roster_id": 4,
                "round": 14,
                "draft_slot": 4,
                "pick_no": 140,
                "metadata": {"position": "DEF"},
                "is_keeper": "false",
                "draft_id": "draft-2026",
            },
            {
                "player_id": "404",
                "picked_by": "user-4",
                "roster_id": 4,
                "round": 15,
                "draft_slot": 4,
                "pick_no": 150,
                "metadata": {},
                "is_keeper": None,
                "draft_id": "draft-2026",
            },
        ]
    )

    assert rows[0].platform_draft_id == "draft-2026"
    assert rows[0].platform_player_id == "9999"
    assert rows[0].picked_by_user_id == "user-8"
    assert rows[0].platform_roster_id == "8"
    assert rows[0].round == 2
    assert rows[0].draft_slot == 5
    assert rows[0].pick_no == 16
    assert rows[0].is_keeper is True
    assert rows[0].metadata["position"] == "WR"
    assert rows[1].platform_player_id == "IND"
    assert rows[1].picked_by_user_id is None
    assert rows[1].is_keeper is False
    assert rows[2].is_keeper is None


def test_client_uses_exact_weekly_and_draft_pick_resources():
    matchup_payload = [
        {"roster_id": 1, "matchup_id": 1, "players": ["101"], "starters": ["101"], "points": 10}
    ]
    transaction_payload = [
        {"transaction_id": "tx-3", "type": "free_agent", "status": "complete", "leg": 2, "adds": {"202": 1}}
    ]
    pick_payload = [
        {
            "draft_id": "draft-test",
            "player_id": "303",
            "picked_by": "user-1",
            "roster_id": 1,
            "round": 1,
            "draft_slot": 1,
            "pick_no": 1,
            "is_keeper": False,
        }
    ]
    payloads = {
        "/v1/league/league-test/matchups/2": matchup_payload,
        "/v1/league/league-test/transactions/2": transaction_payload,
        "/v1/draft/draft-test/picks": pick_payload,
    }
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        payload = payloads.get(request.url.path)
        return httpx.Response(200 if payload is not None else 404, json=payload if payload is not None else {})

    http = httpx.Client(base_url="https://api.sleeper.app/v1/", transport=httpx.MockTransport(handler))
    client = SleeperClient(client=http)

    weekly = client.fetch_weekly_state("league-test", 2)
    picks = client.fetch_draft_picks("draft-test")

    assert weekly.platform == "SLEEPER"
    assert weekly.platform_league_id == "league-test"
    assert weekly.week == 2
    assert weekly.matchups[0].platform_roster_id == "1"
    assert weekly.transactions[0].adds == {"202": "1"}
    assert picks[0].platform_player_id == "303"
    assert seen == [
        "/v1/league/league-test/matchups/2",
        "/v1/league/league-test/transactions/2",
        "/v1/draft/draft-test/picks",
    ]


def test_client_rejects_invalid_week_before_request():
    http = httpx.Client(
        base_url="https://api.sleeper.app/v1/",
        transport=httpx.MockTransport(lambda request: httpx.Response(500)),
    )
    client = SleeperClient(client=http)

    with pytest.raises(ValueError, match="positive integer"):
        client.fetch_weekly_state("league-test", 0)


def test_client_rejects_empty_object_where_list_resource_is_required():
    http = httpx.Client(
        base_url="https://api.sleeper.app/v1/",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
    )
    client = SleeperClient(client=http)

    with pytest.raises(ValueError, match="malformed draft picks"):
        client.fetch_draft_picks("draft-test")
