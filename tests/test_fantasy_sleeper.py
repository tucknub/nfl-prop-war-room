from __future__ import annotations

import httpx

from src.fantasy.sleeper import SleeperClient, SleeperLeagueBundle, normalize_sleeper_bundle


def _bundle(*, league, users, rosters, draft):
    return SleeperLeagueBundle(league=league, users=users, rosters=rosters, drafts=[draft])


def _ffl_bundle():
    return _bundle(
        league={
            "league_id": "ffl-2026",
            "name": "Franchise Football League",
            "season": "2026",
            "status": "pre_draft",
            "total_rosters": 10,
            "previous_league_id": "ffl-2025",
            "roster_positions": ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DEF", "BN", "BN", "BN", "BN", "BN", "BN", "BN"],
            "scoring_settings": {"rec": 1, "pass_td": 6, "pass_int": -2},
            "settings": {
                "waiver_budget": 100,
                "max_keepers": 1,
                "playoff_teams": 6,
                "playoff_week_start": 15,
                "trade_deadline": 12,
                "reserve_slots": 1,
                "draft_rounds": 3,
            },
        },
        users=[{"user_id": "me", "display_name": "Owner", "is_owner": True, "metadata": {"team_name": "Team"}}],
        rosters=[{"roster_id": 1, "owner_id": "me", "players": None, "starters": ["0"] * 9, "reserve": None, "settings": {}}],
        draft={
            "draft_id": "ffl-draft",
            "status": "pre_draft",
            "type": "snake",
            "start_time": 1788624000000,
            "draft_order": None,
            "settings": {"rounds": 16, "teams": 10, "slots_qb": 1, "slots_rb": 2, "slots_wr": 3, "slots_te": 1, "slots_flex": 1, "slots_def": 1, "slots_bn": 7},
        },
    )


def _papa_bundle():
    return _bundle(
        league={
            "league_id": "papa-2026",
            "name": "Papa Johns #2",
            "season": "2026",
            "status": "pre_draft",
            "total_rosters": 12,
            "previous_league_id": "papa-2025",
            "roster_positions": ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "FLEX", "BN", "BN", "BN", "BN", "BN", "BN"],
            "scoring_settings": {
                "rec": 1,
                "pass_td": 6,
                "pass_int": -1,
                "fgm_50p": 5,
                "def_st_td": 6,
            },
            "settings": {
                "waiver_budget": 150,
                "max_keepers": 1,
                "playoff_teams": 6,
                "playoff_week_start": 15,
                "trade_deadline": 12,
                "reserve_slots": 1,
                "draft_rounds": 3,
            },
        },
        users=[{"user_id": "me", "display_name": "Owner", "is_owner": False, "metadata": {}}],
        rosters=[{"roster_id": 2, "owner_id": "me", "players": [], "starters": ["0"] * 9, "reserve": None, "settings": {}}],
        draft={
            "draft_id": "papa-draft",
            "status": "pre_draft",
            "type": "snake",
            "start_time": 1788710400000,
            "draft_order": None,
            "settings": {
                "rounds": 15,
                "teams": 12,
                "slots_qb": 1,
                "slots_rb": 2,
                "slots_wr": 3,
                "slots_te": 1,
                "slots_flex": 2,
                "slots_bn": 6,
                "enforce_position_limits": 1,
                "position_limit_qb": 3,
            },
        },
    )


def test_ffl_uses_current_1qb_rules_and_draft_resource():
    state = normalize_sleeper_bundle(_ffl_bundle(), current_user_id="me")

    assert state.name == "Franchise Football League"
    assert state.team_count == 10
    assert state.my_platform_roster_id == "1"
    assert state.rules.starter_positions == ("QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DEF")
    assert "SUPER_FLEX" not in state.rules.roster_positions
    assert state.rules.waiver_budget == 100
    assert state.rules.max_keepers == 1
    assert state.rules.reserve_slots == 1
    assert state.draft is not None
    assert state.draft.rounds == 16
    assert state.draft.rounds != state.rules.raw_settings["draft_rounds"]
    assert state.rules_ready is True
    assert state.draft_ready is True
    assert state.ownership_ready is False


def test_papa_preserves_distinct_rules_and_classifies_qb_limit_as_draft_only():
    state = normalize_sleeper_bundle(_papa_bundle(), current_user_id="me")

    assert state.team_count == 12
    assert state.my_platform_roster_id == "2"
    assert state.rules.starter_positions == ("QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "FLEX")
    assert "K" not in state.rules.roster_positions
    assert "DEF" not in state.rules.roster_positions
    assert state.rules.scoring_settings["fgm_50p"] == 5
    assert state.rules.scoring_settings["def_st_td"] == 6
    assert state.rules.reserve_slots == 1
    assert state.rules.position_limits == {}
    assert state.rules.waiver_budget == 150
    assert state.draft is not None
    assert state.draft.rounds == 15
    assert state.draft.enforce_position_limits is True
    assert state.draft.position_limits["QB"] == 3
    assert state.ownership_ready is False


def test_league_rules_fingerprint_is_deterministic_and_league_specific():
    ffl_a = normalize_sleeper_bundle(_ffl_bundle(), current_user_id="me")
    ffl_b = normalize_sleeper_bundle(_ffl_bundle(), current_user_id="me")
    papa = normalize_sleeper_bundle(_papa_bundle(), current_user_id="me")

    assert ffl_a.rules_fingerprint == ffl_b.rules_fingerprint
    assert ffl_a.rules_fingerprint != papa.rules_fingerprint


def test_completed_draft_with_real_players_initializes_ownership():
    bundle = _ffl_bundle()
    draft = {**bundle.drafts[0], "status": "complete"}
    rosters = [{**bundle.rosters[0], "players": ["123", "456"], "starters": ["123"]}]
    state = normalize_sleeper_bundle(
        SleeperLeagueBundle(bundle.league, bundle.users, rosters, [draft]),
        current_user_id="me",
    )

    assert state.ownership_ready is True


def test_client_uses_public_read_only_league_resources():
    ffl = _ffl_bundle()
    payloads = {
        "/v1/league/test": {**ffl.league, "league_id": "test"},
        "/v1/league/test/users": ffl.users,
        "/v1/league/test/rosters": ffl.rosters,
        "/v1/league/test/drafts": ffl.drafts,
    }
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        payload = payloads.get(request.url.path)
        return httpx.Response(200 if payload is not None else 404, json=payload or {})

    http = httpx.Client(base_url="https://api.sleeper.app/v1/", transport=httpx.MockTransport(handler))
    client = SleeperClient(client=http)
    bundle = client.fetch_league_bundle("test")

    assert bundle.league["name"] == "Franchise Football League"
    assert seen == [
        "/v1/league/test",
        "/v1/league/test/users",
        "/v1/league/test/rosters",
        "/v1/league/test/drafts",
    ]


def test_client_discovers_user_leagues_and_player_catalog():
    payloads = {
        "/v1/user/tuck": {
            "user_id": "u1",
            "username": "tuck",
            "display_name": "Tuck",
        },
        "/v1/user/u1/leagues/nfl/2026": [
            {
                "league_id": "l1",
                "name": "League One",
                "season": "2026",
                "total_rosters": 12,
            },
            {
                "league_id": "",
                "name": "Malformed",
            },
        ],
        "/v1/players/nfl": {
            "p1": {
                "player_id": "p1",
                "full_name": "Player One",
                "position": "RB",
                "team": "IND",
            }
        },
    }
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        payload = payloads.get(request.url.path)
        return httpx.Response(200 if payload is not None else 404, json=payload or {})

    http = httpx.Client(
        base_url="https://api.sleeper.app/v1/",
        transport=httpx.MockTransport(handler),
    )
    client = SleeperClient(client=http)

    user = client.fetch_user("tuck")
    leagues = client.fetch_user_leagues(user["user_id"], season="2026")
    players = client.fetch_players()

    assert user["user_id"] == "u1"
    assert [row["league_id"] for row in leagues] == ["l1"]
    assert players["p1"]["full_name"] == "Player One"
    assert seen == [
        "/v1/user/tuck",
        "/v1/user/u1/leagues/nfl/2026",
        "/v1/players/nfl",
    ]


def test_user_discovery_rejects_malformed_user_and_league_shapes():
    responses = [
        None,
        {},
    ]

    for payload in responses:
        def handler(request: httpx.Request, payload=payload) -> httpx.Response:
            return httpx.Response(200, json=payload)

        http = httpx.Client(
            base_url="https://api.sleeper.app/v1/",
            transport=httpx.MockTransport(handler),
        )
        client = SleeperClient(client=http)

        try:
            client.fetch_user("tuck")
        except ValueError:
            pass
        else:
            raise AssertionError("malformed Sleeper user must fail closed")


def test_client_fetches_trending_players_with_expected_query_params():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            (
                request.url.path,
                request.url.params.get("lookback_hours"),
                request.url.params.get("limit"),
            )
        )
        return httpx.Response(
            200,
            json=[
                {"player_id": "p1", "count": 42},
                {"player_id": "p2", "count": 17},
                {"player_id": "p1", "count": 99},
                {"player_id": "", "count": 5},
            ],
        )

    http = httpx.Client(
        base_url="https://api.sleeper.app/v1/",
        transport=httpx.MockTransport(handler),
    )
    client = SleeperClient(client=http)

    rows = client.fetch_trending_players(
        "add",
        lookback_hours=48,
        limit=100,
    )

    assert [(row.player_id, row.count) for row in rows] == [
        ("p1", 42),
        ("p2", 17),
    ]
    assert seen == [
        ("/v1/players/nfl/trending/add", "48", "100"),
    ]


def test_client_rejects_invalid_trending_parameters():
    http = httpx.Client(
        base_url="https://api.sleeper.app/v1/",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(500)
        ),
    )
    client = SleeperClient(client=http)

    for args in (
        ("move", 24, 50),
        ("add", 0, 50),
        ("add", 24, 0),
        ("add", 169, 50),
        ("add", 24, 201),
    ):
        trend_type, lookback_hours, limit = args
        try:
            client.fetch_trending_players(
                trend_type,
                lookback_hours=lookback_hours,
                limit=limit,
            )
        except ValueError:
            pass
        else:
            raise AssertionError("invalid trending parameters must fail before HTTP")
