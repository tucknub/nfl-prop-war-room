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


def test_knockout_espn_connect_is_single_submit_form() -> None:
    source = _source("dashboard/pages/08_Knockout_Fantasy_War_Room.py")

    assert 'with st.form("knockout_espn_connect_form"' in source
    assert 'st.form_submit_button(' in source
    assert 'f"Connect {configured_league_name}"' in source
    assert '"Find my leagues"' not in source
    assert '"Use a different ESPN league"' not in source


def test_configured_espn_league_disables_manual_roster_intake() -> None:
    source = _source("dashboard/pages/08_Knockout_Fantasy_War_Room.py")

    assert "the previous manual roster was cleared and Elwood TKO is waiting for ESPN sync." in source
    assert "Manual roster upload is disabled for this league" in source
    configured_guard = source.index('if str(league.get("espn_league_id") or "").strip():')
    manual_upload = source.index('st.file_uploader("Draft roster CSV"')
    assert configured_guard < manual_upload


def test_knockout_page_reloads_espn_adapter() -> None:
    source = _source("dashboard/pages/08_Knockout_Fantasy_War_Room.py")

    reload_call = source.index("espn_module = importlib.reload(espn_module)")
    client_import = source.index("from src.fantasy.espn import (")
    assert reload_call < client_import
    assert '"AWAITING_ESPN": "Waiting for ESPN"' in source


def test_knockout_page_reloads_engine_and_sync_modules() -> None:
    source = _source("dashboard/pages/08_Knockout_Fantasy_War_Room.py")

    assert "engine = importlib.reload(engine_module)" in source
    assert "espn_sync = importlib.reload(espn_sync_module)" in source


def test_knockout_connected_page_is_live_and_text_readable() -> None:
    source = _source("dashboard/pages/08_Knockout_Fantasy_War_Room.py")

    assert "show_data_status=False" in source
    assert "def _auto_sync_due" in source
    assert "max_age_seconds: int = 900" in source
    assert "Auto-sync ESPN Knockout league" in source
    assert "auto-refresh every 15 min" in source
    assert 'score_label = "Not started" if source_score is None' in source
    assert 'st.table(roster_table[["Player", "Pos", "NFL"]])' in source


def test_connected_espn_is_authoritative_for_roster_and_faab() -> None:
    source = _source("dashboard/pages/08_Knockout_Fantasy_War_Room.py")

    assert 'if espn_connection:' in source
    assert '"Roster / FAAB updates"' in source
    assert "No manual roster or FAAB entry is needed." in source
    assert "ESPN is the authoritative roster and FAAB source" in source
