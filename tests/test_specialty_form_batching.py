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
