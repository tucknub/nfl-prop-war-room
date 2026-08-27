from __future__ import annotations

import httpx
import pytest

from src.fantasy.yahoo import (
    DEFAULT_YAHOO_REDIRECT_URI,
    YahooFantasyClient,
    YahooFantasyError,
    YahooOAuthClient,
    YahooOAuthConfig,
    build_yahoo_oauth_state,
    validate_yahoo_oauth_state,
)


CLIENT_ID = "client-id"
CLIENT_SECRET = "client-secret-value"
TEAM_KEY = "461.l.1000.t.1"
LEAGUE_KEY = "461.l.1000"


def test_yahoo_oauth_state_round_trip_and_expiry():
    state = build_yahoo_oauth_state(CLIENT_SECRET, now_seconds=1_000)

    payload = validate_yahoo_oauth_state(
        state,
        CLIENT_SECRET,
        now_seconds=1_100,
    )

    assert payload["purpose"] == "fantasy-hq-yahoo"
    assert payload["iat"] == 1_000

    with pytest.raises(YahooFantasyError, match="expired"):
        validate_yahoo_oauth_state(
            state,
            CLIENT_SECRET,
            now_seconds=2_000,
            max_age_seconds=300,
        )


def test_yahoo_oauth_state_rejects_tampering():
    state = build_yahoo_oauth_state(CLIENT_SECRET, now_seconds=1_000)
    encoded, signature = state.split(".", 1)
    tampered = encoded + "." + ("x" + signature[1:])

    with pytest.raises(YahooFantasyError, match="signature"):
        validate_yahoo_oauth_state(
            tampered,
            CLIENT_SECRET,
            now_seconds=1_010,
        )


def test_yahoo_authorization_url_uses_exact_callback_and_state():
    config = YahooOAuthConfig(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
    )

    url = config.authorization_url(state="signed-state")

    assert url.startswith("https://api.login.yahoo.com/oauth2/request_auth?")
    assert "client_id=client-id" in url
    assert "response_type=code" in url
    assert "state=signed-state" in url
    assert "redirect_uri=https%3A%2F%2Fpropwar.streamlit.app%2Ffantasy-hq" in url
    assert config.redirect_uri == DEFAULT_YAHOO_REDIRECT_URI


def test_yahoo_token_exchange_uses_basic_auth_and_no_redirects():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.url == "https://api.login.yahoo.com/oauth2/get_token"
        assert request.method == "POST"
        assert request.headers["authorization"].startswith("Basic ")
        body = request.content.decode()
        assert "grant_type=authorization_code" in body
        assert "code=abc123" in body
        return httpx.Response(
            200,
            json={
                "access_token": "access",
                "refresh_token": "refresh",
                "expires_in": 3600,
                "token_type": "bearer",
            },
        )

    config = YahooOAuthConfig(CLIENT_ID, CLIENT_SECRET)
    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = YahooOAuthClient(config, client=http)

    token = client.exchange_code("abc123")

    assert token.access_token == "access"
    assert token.refresh_token == "refresh"
    assert token.expires_in == 3600
    assert len(seen) == 1


def test_yahoo_refresh_token_uses_refresh_grant():
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode()
        assert "grant_type=refresh_token" in body
        assert "refresh_token=old-refresh" in body
        return httpx.Response(
            200,
            json={
                "access_token": "new-access",
                "refresh_token": "new-refresh",
                "expires_in": 3600,
                "token_type": "bearer",
            },
        )

    config = YahooOAuthConfig(CLIENT_ID, CLIENT_SECRET)
    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = YahooOAuthClient(config, client=http)

    token = client.refresh("old-refresh")

    assert token.access_token == "new-access"
    assert token.refresh_token == "new-refresh"


def _teams_payload():
    return {
        "fantasy_content": {
            "users": {
                "0": {
                    "user": [
                        {"guid": "guid"},
                        {
                            "games": {
                                "0": {
                                    "game": [
                                        {"game_key": "461", "code": "nfl"},
                                        {
                                            "teams": {
                                                "0": {
                                                    "team": [
                                                        [
                                                            {"team_key": TEAM_KEY},
                                                            {"team_id": "1"},
                                                            {"name": "Dad League Team"},
                                                            {"url": "https://football.fantasysports.yahoo.com/f1/1000/1"},
                                                        ],
                                                        {"managers": {"0": {"manager": {"nickname": "Tuck"}}}},
                                                    ]
                                                },
                                                "count": 1,
                                            }
                                        },
                                    ]
                                },
                                "count": 1,
                            }
                        },
                    ]
                },
                "count": 1,
            }
        }
    }


def _roster_payload():
    return {
        "fantasy_content": {
            "team": [
                {"team_key": TEAM_KEY},
                {
                    "roster": {
                        "0": {
                            "players": {
                                "0": {
                                    "player": [
                                        [
                                            {"player_key": "461.p.30121"},
                                            {"player_id": "30121"},
                                            {
                                                "name": {
                                                    "full": "Jonathan Taylor",
                                                    "first": "Jonathan",
                                                    "last": "Taylor",
                                                }
                                            },
                                            {"editorial_team_abbr": "Ind"},
                                            {"display_position": "RB"},
                                            {"status": "Q"},
                                        ],
                                        {"selected_position": {"position": "RB"}},
                                    ]
                                },
                                "1": {
                                    "player": [
                                        [
                                            {"player_key": "461.p.99999"},
                                            {"name": {"full": "Bench Player"}},
                                            {"editorial_team_abbr": "FA"},
                                            {"display_position": "WR"},
                                        ],
                                        {"selected_position": {"position": "BN"}},
                                    ]
                                },
                                "count": 2,
                            }
                        }
                    }
                },
            ]
        }
    }


def _league_payload():
    return {
        "fantasy_content": {
            "league": [
                [
                    {"league_key": LEAGUE_KEY},
                    {"league_id": "1000"},
                    {"name": "Dad's Yahoo League"},
                    {"season": "2026"},
                    {"num_teams": 12},
                    {"current_week": 1},
                    {"draft_status": "postdraft"},
                ],
                {
                    "settings": [
                        {"scoring_type": "head"},
                        {"draft_type": "live_standard"},
                    ]
                },
            ]
        }
    }


def test_yahoo_fantasy_client_discovers_teams_roster_and_league():
    payloads = {
        "/fantasy/v2/users;use_login=1/games;game_keys=nfl/teams": _teams_payload(),
        f"/fantasy/v2/team/{TEAM_KEY}/roster": _roster_payload(),
        f"/fantasy/v2/league/{LEAGUE_KEY};out=settings": _league_payload(),
    }
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.path, request.url.params.get("format")))
        payload = payloads.get(request.url.path)
        return httpx.Response(200 if payload is not None else 404, json=payload or {})

    http = httpx.Client(
        base_url="https://fantasysports.yahooapis.com/fantasy/v2/",
        transport=httpx.MockTransport(handler),
    )
    client = YahooFantasyClient("access-token", client=http)

    teams = client.fetch_user_nfl_teams()
    roster = client.fetch_team_roster(TEAM_KEY)
    league = client.fetch_league(LEAGUE_KEY)

    assert len(teams) == 1
    assert teams[0].team_key == TEAM_KEY
    assert teams[0].league_key == LEAGUE_KEY
    assert teams[0].name == "Dad League Team"

    assert [player.name for player in roster] == ["Jonathan Taylor", "Bench Player"]
    assert roster[0].display_position == "RB"
    assert roster[0].selected_position == "RB"
    assert roster[0].nfl_team == "Ind"
    assert roster[1].selected_position == "BN"

    assert league.league_key == LEAGUE_KEY
    assert league.name == "Dad's Yahoo League"
    assert league.season == "2026"
    assert league.num_teams == 12
    assert league.current_week == 1
    assert league.scoring_type == "head"
    assert league.draft_status == "postdraft"

    assert seen == [
        ("/fantasy/v2/users;use_login=1/games;game_keys=nfl/teams", "json"),
        (f"/fantasy/v2/team/{TEAM_KEY}/roster", "json"),
        (f"/fantasy/v2/league/{LEAGUE_KEY};out=settings", "json"),
    ]


def test_yahoo_fantasy_client_rejects_non_fantasy_payload():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"not_fantasy_content": {}})

    http = httpx.Client(
        base_url="https://fantasysports.yahooapis.com/fantasy/v2/",
        transport=httpx.MockTransport(handler),
    )
    client = YahooFantasyClient("access-token", client=http)

    with pytest.raises(YahooFantasyError, match="malformed"):
        client.fetch_user_nfl_teams()
