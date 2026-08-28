from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_fantasy_uses_versioned_selector_and_syncs_legacy_context() -> None:
    source = _source("dashboard/pages/11_Fantasy_HQ.py")

    assert (
        'FANTASY_LEAGUE_SELECTOR_KEY = "fantasy_hq_sleeper_league_v2"'
        in source
    )
    assert (
        'LEGACY_FANTASY_LEAGUE_SELECTOR_KEY = "fantasy_hq_sleeper_league"'
        in source
    )
    assert "choose_sleeper_league_label(" in source
    assert "key=FANTASY_LEAGUE_SELECTOR_KEY" in source
    assert (
        "st.session_state[LEGACY_FANTASY_LEAGUE_SELECTOR_KEY] = selected_label"
        in source
    )


def test_player_command_defaults_to_real_context_and_excludes_demo_from_exposure() -> None:
    source = _source("dashboard/player_command_owner.py")

    assert 'DEMO_LEAGUE_NAMES = {"test league", "mock league", "demo league"}' in source
    assert "real_leagues = tuple(" in source
    assert "demo_leagues = tuple(" in source
    assert "real_states = tuple(" in source
    assert 'f"player_command_league_v2_{propwar_player_id}"' in source
    assert "choose_sleeper_league_label(" in source
    assert "card_states = (" in source
    assert "f\"{card.my_league_count}/{len(card_states)} leagues\"" in source


def test_player_command_does_not_show_blank_owner_for_known_other_roster() -> None:
    source = _source("dashboard/player_command_owner.py")

    assert '"Other roster"' in source
    assert "card.selected_league_status == \"OTHER\"" in source
    assert "card.selected_league_owner or 'another roster'" in source
