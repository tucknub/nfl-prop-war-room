from __future__ import annotations

import httpx
import pytest

from src.fantasy.espn import (
    EspnCredentials,
    EspnFantasyClient,
    normalize_league_snapshot,
    open_credentials,
    seal_credentials,
)


SWID = "{11111111-2222-3333-4444-555555555555}"


def _payload() -> dict:
    return {
        "id": 987654,
        "seasonId": 2026,
        "scoringPeriodId": 1,
        "status": {"currentScoringPeriod": 1, "currentMatchupPeriod": 1},
        "settings": {
            "name": "Elwood TKO",
            "size": 18,
            "isPublic": False,
            "acquisitionSettings": {"acquisitionBudget": 1000},
            "draftSettings": {"slotCount": 14},
        },
        "teams": [
            {
                "id": 7,
                "name": "Tuck Team",
                "owners": [SWID],
                "transactionCounter": {"acquisitionBudgetSpent": 125},
                "roster": {
                    "entries": [
                        {
                            "playerId": 1,
                            "lineupSlotId": 0,
                            "playerPoolEntry": {
                                "player": {
                                    "fullName": "Dak Prescott",
                                    "defaultPositionId": 1,
                                    "proTeamId": 6,
                                    "injuryStatus": "ACTIVE",
                                }
                            },
                        },
                        {
                            "playerId": 2,
                            "lineupSlotId": 20,
                            "playerPoolEntry": {
                                "player": {
                                    "fullName": "Bench Runner",
                                    "defaultPositionId": 2,
                                    "proTeamId": 11,
                                }
                            },
                        },
                    ]
                },
            }
        ],
        "schedule": [
            {
                "matchupPeriodId": 1,
                "home": {"teamId": 7, "totalPoints": 91.25},
                "away": {"teamId": 8, "totalPoints": 88.0},
            }
        ],
    }


def test_credentials_round_trip_is_encrypted() -> None:
    credentials = EspnCredentials("x" * 80, SWID)
    envelope = seal_credentials(credentials, "very-long-test-secret-value")
    assert "11111111" not in envelope
    assert "xxxxxxxx" not in envelope
    assert open_credentials(envelope, "very-long-test-secret-value") == credentials.normalized()


def test_normalize_league_snapshot_identifies_owner_roster_and_faab() -> None:
    snapshot = normalize_league_snapshot(_payload(), swid=SWID)

    assert snapshot["league_name"] == "Elwood TKO"
    assert snapshot["team_count"] == 18
    assert snapshot["team_id"] == 7
    assert snapshot["faab_remaining"] == 875
    assert snapshot["current_week"] == 1
    assert snapshot["current_score"] == pytest.approx(91.25)
    assert snapshot["roster"][0]["player"] == "Dak Prescott"
    assert snapshot["roster"][0]["nfl_team"] == "DAL"
    assert snapshot["roster"][1]["lineup_role"] == "Bench"


def test_default_position_ids_are_not_treated_as_lineup_slot_ids() -> None:
    payload = _payload()
    payload["teams"][0]["roster"]["entries"] = [
        {
            "playerId": 10,
            "lineupSlotId": 20,
            "playerPoolEntry": {
                "player": {
                    "fullName": "Quarter Back",
                    "defaultPositionId": 1,
                    "proTeamId": 6,
                }
            },
        },
        {
            "playerId": 11,
            "lineupSlotId": 20,
            "playerPoolEntry": {
                "player": {
                    "fullName": "Wide Receiver",
                    "defaultPositionId": 3,
                    "proTeamId": 4,
                }
            },
        },
        {
            "playerId": 12,
            "lineupSlotId": 20,
            "playerPoolEntry": {
                "player": {
                    "fullName": "Tight End",
                    "defaultPositionId": 4,
                    "proTeamId": 19,
                }
            },
        },
        {
            "playerId": 13,
            "lineupSlotId": 20,
            "playerPoolEntry": {
                "player": {
                    "fullName": "Kicker",
                    "defaultPositionId": 5,
                    "proTeamId": 33,
                }
            },
        },
    ]

    snapshot = normalize_league_snapshot(payload, swid=SWID)

    assert [row["position"] for row in snapshot["roster"]] == [
        "QB",
        "WR",
        "TE",
        "K",
    ]


def test_eligible_slots_are_primary_position_signal() -> None:
    payload = _payload()
    payload["teams"][0]["roster"]["entries"] = [
        {
            "playerId": 20,
            "lineupSlotId": 20,
            "playerPoolEntry": {
                "player": {
                    "fullName": "Slot Tight End",
                    "defaultPositionId": 3,
                    "eligibleSlots": [6, 23, 20, 21],
                    "proTeamId": 19,
                }
            },
        }
    ]

    snapshot = normalize_league_snapshot(payload, swid=SWID)

    assert snapshot["roster"][0]["position"] == "TE"


def test_private_client_uses_read_host_and_cookie_auth() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["cookie"] = request.headers.get("cookie", "")
        return httpx.Response(
            200,
            json=_payload(),
            headers={"content-type": "application/json"},
        )

    transport = httpx.MockTransport(handler)
    credentials = EspnCredentials("x" * 80, SWID)
    with EspnFantasyClient(credentials, transport=transport) as client:
        payload = client.fetch_league(987654, season=2026, views=("mTeam",))

    assert payload["id"] == 987654
    assert seen["url"].startswith(
        "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2026/segments/0/leagues/987654"
    )
    assert "espn_s2=" in seen["cookie"]
    assert "SWID=" in seen["cookie"]


def test_knockout_snapshot_scopes_roster_to_known_team() -> None:
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        seen.append(url)
        payload = _payload()
        if "view=mSettings" in url:
            payload["teams"][0].pop("roster", None)
            payload["teams"][0]["owners"] = ["{00000000-0000-0000-0000-000000000000}"]
            payload.pop("schedule", None)
        elif "view=mRoster" in url:
            payload.pop("settings", None)
            payload.pop("status", None)
            payload.pop("schedule", None)
        elif "view=mMatchupScore" in url:
            payload.pop("settings", None)
            payload.pop("status", None)
            payload["teams"] = []
        return httpx.Response(200, json=payload, headers={"content-type": "application/json"})

    transport = httpx.MockTransport(handler)
    credentials = EspnCredentials("x" * 80, SWID)
    with EspnFantasyClient(credentials, transport=transport) as client:
        snapshot = client.fetch_knockout_snapshot(
            987654,
            season=2026,
            team_id=7,
            swid=SWID,
        )

    assert snapshot["team_id"] == 7
    assert snapshot["roster"][0]["player"] == "Dak Prescott"
    assert snapshot["current_score"] == pytest.approx(91.25)
    assert len(seen) == 3
    roster_url = next(url for url in seen if "view=mRoster" in url)
    assert "scoringPeriodId=1" in roster_url
    assert "rosterForTeamId=7" in roster_url


def test_private_client_retries_with_decoded_s2() -> None:
    cookies_seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        cookie = request.headers.get("cookie", "")
        cookies_seen.append(cookie)
        if "%2F" in cookie:
            return httpx.Response(
                403,
                json={"messages": ["You are not authorized to view this League."]},
                headers={"content-type": "application/json"},
            )
        return httpx.Response(
            200,
            json=_payload(),
            headers={"content-type": "application/json"},
        )

    transport = httpx.MockTransport(handler)
    credentials = EspnCredentials("abc%2Fdef%2Bghi%3D" + "x" * 40, SWID)
    with EspnFantasyClient(credentials, transport=transport) as client:
        payload = client.fetch_league(987654, season=2026, views=("mTeam",))

    assert payload["id"] == 987654
    assert len(cookies_seen) == 2
    assert "%2F" in cookies_seen[0]
    assert "abc/def+ghi=" in cookies_seen[1]
