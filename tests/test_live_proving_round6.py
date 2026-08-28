from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_player_command_renders_predraft_as_expected_state_not_error() -> None:
    source = _source("dashboard/player_command_owner.py")

    assert "if not selected_league.ownership_ready:" in source
    assert 'fan_a.metric("This league", "Pre-draft")' in source
    assert 'fan_b.metric("Current owner", "Not available yet")' in source
    assert "**FANTASY ACTION: WAIT FOR DRAFT**" in source
    assert "This is an expected pre-draft state, not a Fantasy data error." in source


def test_player_command_keeps_real_errors_separate_from_predraft() -> None:
    source = _source("dashboard/player_command_owner.py")

    assert 'st.warning("Fantasy player intelligence could not be built.")' in source
    predraft = source.index("if not selected_league.ownership_ready:")
    generic_error = source.index(
        'st.warning("Fantasy player intelligence could not be built.")'
    )
    assert predraft < generic_error


def test_arb_copy_distinguishes_implied_sum_edge_from_roi() -> None:
    source = _source("dashboard/pages/09_Glitch_Radar.py")

    assert 'meta.append(f"implied-sum edge {edge:.2f}%")' in source
    assert "locked ROI ≈ {locked_roi:.2f}%" in source
    assert '"Feed edge"' not in source
    assert "feed edge" not in source.lower()


def test_arb_edge_prefers_implied_sum_when_present() -> None:
    source = _source("dashboard/pages/09_Glitch_Radar.py")

    helper_start = source.index("def _arb_edge_pct(row: dict)")
    helper_end = source.index("\ndef _render_arb_card", helper_start)
    helper = source[helper_start:helper_end]

    assert 'implied_sum = float(row.get("implied_sum"))' in helper
    assert "return (1.0 - implied_sum) * 100.0" in helper
    assert helper.index('implied_sum = float(row.get("implied_sum"))') < helper.index(
        'for key in ("profit_pct", "arb_pct", "edge_pct")'
    )
