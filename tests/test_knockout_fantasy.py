from __future__ import annotations

import copy

import pytest

from src.knockout import engine, state_store


AUTH = {
    "redirect_uri": "https://propwar.streamlit.app/oauth2callback",
    "cookie_secret": "cookie-secret",
    "client_id": "client-id",
    "client_secret": "client-secret",
    "server_metadata_url": "https://accounts.google.com/.well-known/openid-configuration",
}


def base_state() -> dict:
    return {
        "schema_version": "knockout_live_state_v1",
        "season": 2026,
        "status": "PRE_DRAFT",
        "current_week": 0,
        "faab_remaining": 1000,
        "roster": [],
        "weekly_results": [],
        "eliminations": [],
        "faab_transactions": [],
        "league": {
            "name": None,
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
    }


def roster() -> list[dict[str, str]]:
    return [
        {"player": "QB One", "position": "QB", "nfl_team": "IND"},
        {"player": "QB Two", "position": "QB", "nfl_team": "BUF"},
        {"player": "RB One", "position": "RB", "nfl_team": "IND"},
        {"player": "RB Two", "position": "RB", "nfl_team": "DET"},
        {"player": "RB Three", "position": "RB", "nfl_team": "KC"},
        {"player": "RB Four", "position": "RB", "nfl_team": "PHI"},
        {"player": "WR One", "position": "WR", "nfl_team": "CIN"},
        {"player": "WR Two", "position": "WR", "nfl_team": "MIN"},
        {"player": "WR Three", "position": "WR", "nfl_team": "LA"},
        {"player": "WR Four", "position": "WR", "nfl_team": "MIA"},
        {"player": "TE One", "position": "TE", "nfl_team": "SF"},
        {"player": "TE Two", "position": "TE", "nfl_team": "ARI"},
        {"player": "K One", "position": "K", "nfl_team": "BAL"},
        {"player": "DST One", "position": "D/ST", "nfl_team": "PIT"},
    ]


def test_trade_free_rule_is_hard_invariant() -> None:
    state = base_state()
    assert engine.validate_state(state) is state
    bad = copy.deepcopy(state)
    bad["league"]["trades_allowed"] = True
    with pytest.raises(ValueError, match="trade-free"):
        engine.validate_state(bad)


def test_roster_validation_enforces_size_uniqueness_and_startable_lineup() -> None:
    normalized = engine.validate_roster(roster())
    assert len(normalized) == 14
    assert normalized[-1]["position"] == "DST"

    too_short = roster()[:-1]
    with pytest.raises(ValueError, match="exactly 14"):
        engine.validate_roster(too_short)

    duplicate = roster()
    duplicate[-1] = dict(duplicate[0])
    with pytest.raises(ValueError, match="duplicate"):
        engine.validate_roster(duplicate)


def test_draft_transition_starts_week_one_without_touching_faab() -> None:
    state = base_state()
    updated = engine.record_draft_state(state, roster())
    assert state["roster"] == []
    assert updated["status"] == "ACTIVE"
    assert updated["current_week"] == 1
    assert updated["faab_remaining"] == 1000
    assert len(updated["roster"]) == 14
    assert engine.phase(updated) == "EARLY_SURVIVAL"


def test_survival_week_advances_and_shrinks_field() -> None:
    active = engine.record_draft_state(base_state(), roster())
    updated = engine.record_week_state(
        active,
        user_score=137.4,
        eliminated_team="Team 18",
        user_eliminated=False,
    )
    assert updated["current_week"] == 2
    assert updated["status"] == "ACTIVE"
    assert updated["weekly_results"] == [{"week": 1, "user_score": 137.4, "user_eliminated": False}]
    assert updated["eliminations"] == [{"week": 1, "team": "Team 18"}]
    assert engine.active_team_count(updated) == 17


def test_user_elimination_ends_state_without_advancing_week() -> None:
    active = engine.record_draft_state(base_state(), roster())
    updated = engine.record_week_state(
        active,
        user_score=71.2,
        eliminated_team="My Team",
        user_eliminated=True,
    )
    assert updated["status"] == "ELIMINATED"
    assert updated["current_week"] == 1
    assert engine.phase(updated) == "ELIMINATED"


def test_faab_ledger_cannot_overspend() -> None:
    active = engine.record_draft_state(base_state(), roster())
    updated = engine.record_faab_spend(active, 225, note="Waiver win")
    assert updated["faab_remaining"] == 775
    assert updated["faab_transactions"][0]["amount"] == 225
    with pytest.raises(ValueError, match="exceeds"):
        engine.record_faab_spend(updated, 776)


def test_waiver_transaction_updates_roster_and_faab_together() -> None:
    active = engine.record_draft_state(base_state(), roster())
    updated = engine.record_waiver_transaction(
        active,
        amount=125,
        add_player={"player": "RB New", "position": "RB", "nfl_team": "SEA"},
        drop_player="RB Four",
        note="Won post-elimination waiver",
    )
    assert updated["faab_remaining"] == 875
    names = {row["player"] for row in updated["roster"]}
    assert "RB New" in names
    assert "RB Four" not in names
    tx = updated["faab_transactions"][0]
    assert tx["amount"] == 125
    assert tx["add"] == "RB New"
    assert tx["drop"] == "RB Four"


def test_waiver_transaction_rejects_invalid_drop_or_lineup_break() -> None:
    active = engine.record_draft_state(base_state(), roster())
    with pytest.raises(ValueError, match="not uniquely present"):
        engine.record_waiver_transaction(
            active,
            amount=0,
            add_player={"player": "WR New", "position": "WR", "nfl_team": "SEA"},
            drop_player="Not On Roster",
        )

    with pytest.raises(ValueError, match="required starters"):
        engine.record_waiver_transaction(
            active,
            amount=0,
            add_player={"player": "WR New", "position": "WR", "nfl_team": "SEA"},
            drop_player="K One",
        )


def test_knockout_storage_reuses_private_repo_but_has_separate_path() -> None:
    secrets = {
        "auth": dict(AUTH),
        "PROPWAR_OWNER_EMAIL": "owner@example.com",
        "MARGIN_GITHUB_TOKEN": "token",
        "MARGIN_GITHUB_REPO": "tucknub/propwar-private-state",
    }
    config = state_store.config_from_secrets(secrets)
    assert config is not None
    assert config["repo"] == "tucknub/propwar-private-state"
    assert config["path"] == "knockout/live_state_2026.json"
    assert config["auth_mode"] == "OIDC_OWNER"
