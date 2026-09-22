from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

from src.fantasy.espn import EspnCredentials, EspnFantasyClient


def _player(name: str, position: str, team: str, projected: float | None):
    return SimpleNamespace(
        name=name,
        position=position,
        proTeam=team,
        playerId=hash(name) % 100000,
        injuryStatus="ACTIVE",
        percent_owned=50.0,
        projected_points=projected,
    )


def test_knockout_context_uses_current_boxscore_for_roster_projections(monkeypatch) -> None:
    mine = SimpleNamespace(
        team_id=7,
        team_name="Mine",
        owners=[],
        roster=[_player("QB One", "QB", "DAL", None)],
    )
    other = SimpleNamespace(team_id=8, team_name="Other", owners=[], roster=[])
    box = SimpleNamespace(
        home_team=mine,
        away_team=other,
        home_score=0.0,
        away_score=0.0,
        home_lineup=[_player("QB One", "QB", "DAL", 19.7)],
        away_lineup=[],
    )
    class FakeLeague:
        def __init__(self, **kwargs):
            self.current_week = 1
            self.teams = [mine, other]

        def free_agents(self, **kwargs):
            return [_player("Free Agent", "RB", "TB", 10.5)]

        def box_scores(self, week: int):
            assert week == 1
            return [box]

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
            current_week=1,
            team_id=7,
        )

    assert context["roster_player_metrics"][0]["player"] == "QB One"
    assert context["roster_player_metrics"][0]["projected_points"] == 19.7
    assert context["available_players"][0]["projected_points"] == 10.5
