from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_knockout_page_is_decision_first() -> None:
    source = _source("dashboard/pages/08_Knockout_Fantasy_War_Room.py")

    decision = source.index('"What Should I Do?"')
    rules = source.index('st.expander("League rules"')
    roster = source.index('section("Roster state"')

    assert decision < rules < roster
    assert 'decision_cols[0].metric("Next action"' in source
    assert 'decision_cols[1].metric("Roster risk"' in source
    assert 'decision_cols[2].metric("FAAB posture"' in source
    assert 'decision_cols[3].metric("Teams alive"' in source


def test_knockout_released_roster_flow_is_private_and_fit_only() -> None:
    source = _source("dashboard/pages/08_Knockout_Fantasy_War_Room.py")

    assert '"Eliminated roster → waivers"' in source
    assert "engine.record_released_roster(" in source
    assert "_persist_transition(" in source
    assert "engine.released_roster_fit(state, released_entry)" in source
    assert "Fit is structural only." in source
    assert "does not" in source
    assert "recommend a FAAB bid" in source


def test_knockout_does_not_claim_unvalidated_probability_or_optimal_bid() -> None:
    source = _source("dashboard/pages/08_Knockout_Fantasy_War_Room.py")

    assert "no fake survival probability or optimal bid" in source
    assert "does not claim a weekly survival probability" in source
    assert "player-quality ranking" in source
    assert "V1 is the league-state foundation" not in source
