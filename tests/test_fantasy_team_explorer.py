from __future__ import annotations

from src.fantasy.models import FantasyLeagueState, LeagueRules, Manager, Roster
from src.fantasy.sleeper import SleeperTrendingPlayer
from src.fantasy.team_explorer import HIGH, MEDIUM, build_league_team_profile


CATALOG = {
    "qb1": {"full_name": "QB One", "position": "QB", "team": "IND", "status": "Active", "active": True},
    "rb1": {"full_name": "RB One", "position": "RB", "team": "DET", "status": "Active", "active": True},
    "rb2": {"full_name": "RB Two", "position": "RB", "team": "ATL", "status": "Active", "active": True},
    "rb3": {"full_name": "Free RB", "position": "RB", "team": "CHI", "status": "Active", "active": True},
    "wr1": {"full_name": "WR One", "position": "WR", "team": "PHI", "status": "Active", "active": True},
    "wr2": {"full_name": "WR Two", "position": "WR", "team": "CIN", "status": "Active", "active": True},
    "wr3": {"full_name": "Free WR", "position": "WR", "team": "BUF", "status": "Active", "active": True},
    "te1": {"full_name": "TE One", "position": "TE", "team": "KC", "status": "Active", "active": True},
    "te2": {"full_name": "Free TE", "position": "TE", "team": "BAL", "status": "Active", "active": True},
    "def1": {"full_name": "Defense One", "position": "DEF", "team": "JAX", "status": "Active", "active": True},
    "out_rb": {"full_name": "Out RB", "position": "RB", "team": "MIA", "injury_status": "Out", "active": True},
}


def _league(
    *,
    target_players=("qb1", "rb1", "wr1", "te1"),
    target_starters=("qb1", "rb1", "wr1", "te1"),
    other_players=("rb2", "wr2"),
    ownership_ready=True,
    roster_positions=("QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "BN"),
) -> FantasyLeagueState:
    return FantasyLeagueState(
        platform="SLEEPER",
        platform_league_id="league-1",
        name="League",
        season="2026",
        status="in_season",
        team_count=10,
        previous_platform_league_id=None,
        current_platform_user_id="me",
        my_platform_roster_id="1",
        rules=LeagueRules(
            roster_positions=tuple(roster_positions),
            scoring_settings={"rec": 1},
            waiver_budget=100,
        ),
        draft=None,
        managers=(
            Manager(platform_user_id="me", display_name="Me", team_name="My Team"),
            Manager(platform_user_id="rival", display_name="Rival", team_name="Rival Team"),
        ),
        rosters=(
            Roster(
                platform_roster_id="1",
                platform_user_id="me",
                players=tuple(other_players),
                starters=tuple(other_players[:1]),
                reserve=(),
                taxi=(),
                settings={"wins": 1, "losses": 0, "fpts": 120},
            ),
            Roster(
                platform_roster_id="2",
                platform_user_id="rival",
                players=tuple(target_players),
                starters=tuple(target_starters),
                reserve=(),
                taxi=(),
                settings={"wins": 0, "losses": 1, "fpts": 95},
            ),
        ),
        rules_ready=True,
        draft_ready=True,
        ownership_ready=ownership_ready,
    )


def test_team_explorer_profiles_any_manager_not_only_current_opponent():
    league = _league()

    profile = build_league_team_profile(league, "2", CATALOG)

    assert profile.team_name == "Rival Team"
    assert profile.record == "0-1"
    assert profile.points_for == 95
    assert profile.roster_size == 4
    assert profile.starter_slots == 7
    assert profile.open_starter_slots == 3


def test_team_explorer_surfaces_structural_shopping_areas():
    league = _league(
        target_players=("qb1", "rb1", "wr1", "te1"),
        target_starters=("qb1", "rb1", "wr1", "te1"),
    )

    profile = build_league_team_profile(league, "2", CATALOG)

    need_by_position = {row.position: row for row in profile.needs}
    assert need_by_position["RB"].level == HIGH
    assert need_by_position["WR"].level == HIGH
    assert need_by_position["RB/WR/TE"].level in {HIGH, MEDIUM}


def test_team_explorer_uses_serious_status_as_need_pressure():
    league = _league(
        target_players=("qb1", "out_rb", "rb2", "wr1", "wr2", "te1"),
        target_starters=("qb1", "out_rb", "rb2", "wr1", "wr2", "te1"),
        other_players=(),
    )

    profile = build_league_team_profile(league, "2", CATALOG)

    assert profile.serious_status_count == 1
    rb_needs = [row for row in profile.needs if row.position == "RB"]
    assert rb_needs
    assert rb_needs[0].level == HIGH


def test_team_explorer_does_not_require_backup_defense():
    league = _league(
        target_players=("qb1", "rb1", "rb2", "wr1", "wr2", "te1", "def1"),
        target_starters=("qb1", "rb1", "rb2", "wr1", "wr2", "te1", "def1"),
        roster_positions=("QB", "RB", "RB", "WR", "WR", "TE", "DEF", "BN"),
    )

    profile = build_league_team_profile(league, "2", CATALOG)

    assert all(need.position != "DEF" for need in profile.needs)


def test_team_explorer_targets_only_available_players_matching_needs():
    league = _league()
    trends = (
        SleeperTrendingPlayer(player_id="wr3", count=250),
        SleeperTrendingPlayer(player_id="rb3", count=100),
        SleeperTrendingPlayer(player_id="te2", count=50),
    )

    profile = build_league_team_profile(
        league,
        "2",
        CATALOG,
        trends=trends,
    )

    ids = [row.sleeper_player_id for row in profile.targets]
    assert "rb3" in ids
    assert "wr3" in ids
    assert "rb2" not in ids
    assert "wr2" not in ids
    assert profile.targets[0].trend_count >= profile.targets[-1].trend_count


def test_team_explorer_targets_fail_closed_when_ownership_not_ready():
    league = _league(ownership_ready=False)

    profile = build_league_team_profile(league, "2", CATALOG)

    assert profile.targets == ()


def test_fantasy_hq_exposes_team_explorer_and_remembered_sleeper_username():
    from pathlib import Path

    page = (
        Path(__file__).resolve().parents[1]
        / "dashboard"
        / "pages"
        / "11_Fantasy_HQ.py"
    ).read_text(encoding="utf-8")

    assert '"Trades"' in page
    assert 'st.markdown("#### Manager Intelligence")' in page
    assert "build_league_team_profile" in page
    assert "Likely shopping" in page
    assert "Available players that fit" in page
    assert "remembered_sleeper_username" in page
    assert "store_sleeper_username" in page

    owner_preferences = (
        Path(__file__).resolve().parents[1]
        / "dashboard"
        / "owner_preferences.py"
    ).read_text(encoding="utf-8")
    assert 'SLEEPER_USERNAME_SESSION_KEY = "fantasy_hq_sleeper_username"' in owner_preferences
    assert 'SLEEPER_USERNAME_QUERY_KEY = "fh_sleeper"' in owner_preferences
    assert "private_sleeper_username()" in owner_preferences
