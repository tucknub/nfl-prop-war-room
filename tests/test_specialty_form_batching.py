from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_pdl_field_is_automatic_not_manual_preview() -> None:
    source = (
        ROOT / "dashboard" / "pages" / "07_PDL_War_Room.py"
    ).read_text(encoding="utf-8")

    assert 'section("PDL sync status"' in source
    assert 'fetch_and_reconcile(stored_state)' in source
    assert 'margin_pool_preview_form' not in source
    assert 'Opponent field CSV' not in source


def test_pdl_authoritative_pick_write_requires_confirmation() -> None:
    source = (
        ROOT / "dashboard" / "pages" / "07_PDL_War_Room.py"
    ).read_text(encoding="utf-8")

    assert 'with st.form("margin_week_completion_form", clear_on_submit=False):' in source
    assert 'confirm_final_margin = st.checkbox(' in source
    assert 'complete_week = st.form_submit_button(' in source
    assert 'if complete_week and not confirm_final_margin:' in source
    assert 'acknowledge = st.checkbox(' in source
    assert 'disabled=not (authorized and acknowledge)' in source
    assert 'margin_pool_preview_persist_form' not in source


def test_knockout_mutation_workflows_batch_widget_edits() -> None:
    source = (
        ROOT / "dashboard" / "pages" / "08_Knockout_Fantasy_War_Room.py"
    ).read_text(encoding="utf-8")

    assert 'with st.form("knockout_waiver_transaction_form", clear_on_submit=False):' in source
    assert 'record_transaction = st.form_submit_button(' in source
    assert '"Record waiver transaction",\n        disabled=' not in source
    assert 'if record_transaction and not can_record_transaction:' in source
    assert 'with st.form("knockout_week_result_form", clear_on_submit=False):' in source
    assert 'complete_week = st.form_submit_button(' in source
    assert 'key="knockout_complete_week"' not in source
    assert 'if complete_week and not can_record:' in source
