from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_margin_field_preview_batches_multi_field_edits() -> None:
    source = (
        ROOT / "dashboard" / "pages" / "07_Margin_War_Room.py"
    ).read_text(encoding="utf-8")

    assert 'with st.form("margin_pool_preview_form", clear_on_submit=False):' in source
    assert 'validate_preview = st.form_submit_button(' in source
    assert 'disabled=not bool(field_text.strip())' not in source
    assert 'if validate_preview and not field_text.strip():' in source


def test_margin_authoritative_writes_require_confirmation_forms() -> None:
    source = (
        ROOT / "dashboard" / "pages" / "07_Margin_War_Room.py"
    ).read_text(encoding="utf-8")

    assert 'with st.form("margin_week_completion_form", clear_on_submit=False):' in source
    assert 'confirm_final_margin = st.checkbox(' in source
    assert 'complete_week = st.form_submit_button(' in source
    assert 'if complete_week and not confirm_final_margin:' in source
    assert 'with st.form("margin_pool_preview_persist_form", clear_on_submit=False):' in source
    assert 'confirm_pool_field = st.checkbox(' in source
    assert 'save_validated_field = st.form_submit_button(' in source
    assert 'if save_validated_field and not confirm_pool_field:' in source
    assert 'preview_base_state = json.loads(st.session_state["margin_pool_preview_base_state"])' in source
    assert '_calculate_snapshot.clear()' in source


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
