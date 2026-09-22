from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

from src.fantasy.espn import EspnCredentials, EspnFantasyClient


def _player(name: str, position: str, team: str, *, week3: float | None):
    stats = {3: {"projected_points": week3}} if week3 is not None else {}
    return SimpleNamespace(
        name=name,
        position=position,
        proTeam=team,
        playerId=hash(name) % 100000,
        injuryStatus="ACTIVE",
        percent_owned=50.0,
        projected_points=None,
        stats=stats,
    )


def test_knockout_context_uses_roster_stats_and_team_scores_without_matchups(monkeypatch) -> None:
    mine = SimpleNamespace(
        team_id=7,
        team_name="Mine",
        owners=[],
        roster=[_player("QB One", "QB", "DAL", week3=19.7)],
        scores=[120.0, 110.0, 0.0],
    )
    chopped_week1 = SimpleNamespace(
        team_id=8,
        team_name="Week One Chop",
        owners=[],
        roster=[],
        scores=[50.0, 0.0, 0.0],
    )
    chopped_week2 = SimpleNamespace(
        team_id=9,
        team_name="Week Two Chop",
        owners=[],
        roster=[],
        scores=[90.0, 40.0, 0.0],
    )

    class FakeLeague:
        def __init__(self, **kwargs):
            self.current_week = 3
            self.teams = [mine, chopped_week1, chopped_week2]

        def free_agents(self, **kwargs):
            return [_player("Free Agent", "RB", "TB", week3=10.5)]

        def box_scores(self, week: int):
            return []

    package = ModuleType("espn_api")
    football = ModuleType("espn_api.football")
    football.League = FakeLeague
    monkeypatch.setitem(sys.modules, "espn_api", package)
    monkeypatch.setitem(sys.modules, "espn_api.football", football)

    credentials = EspnCredentials("x" * 80, "{11111111-2222-3333-4444-555555555555}")
    with EspnFantasyClient(credentials) as client:
        context = client._fetch_knockout_league_context_with_espn_api(
            60191612,
            season=2026,
            current_week=3,
            team_id=7,
        )

    assert context["roster_player_metrics"][0]["projected_points"] == 19.7
    assert context["available_players"][0]["projected_points"] == 10.5
    assert [row["team"] for row in context["detected_eliminations"]] == [
        "Week One Chop",
        "Week Two Chop",
    ]
    assert [row["score"] for row in context["detected_eliminations"]] == [50.0, 40.0]
    assert len(context["league_week_scores"]) == 6
