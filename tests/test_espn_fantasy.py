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
                                    "defaultPositionId": 0,
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
