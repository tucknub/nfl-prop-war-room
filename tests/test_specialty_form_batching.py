from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_margin_field_preview_batches_multi_field_edits() -> None:
    source = (
        ROOT / "dashboard" / "pages" / "07_Margin_War_Room.py"
    ).read_text(encoding="utf-8")

    assert 'with st.form("margin_pool_preview_form", clear_on_submit=False):' in source
    assert 'validate_preview = st.form_submit_button(' in source


def test_knockout_mutation_workflows_batch_widget_edits() -> None:
    source = (
        ROOT / "dashboard" / "pages" / "08_Knockout_Fantasy_War_Room.py"
    ).read_text(encoding="utf-8")

    assert 'with st.form("knockout_waiver_transaction_form", clear_on_submit=False):' in source
    assert 'record_transaction = st.form_submit_button(' in source
    assert 'with st.form("knockout_week_result_form", clear_on_submit=False):' in source
    assert 'complete_week = st.form_submit_button(' in source
