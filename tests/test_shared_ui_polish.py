from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_shared_ui_uses_compact_dashboard_visual_system() -> None:
    source = (ROOT / "dashboard" / "research_ui.py").read_text(encoding="utf-8")

    assert "--pw-radius-lg:12px" in source
    assert '[data-testid="stTabs"] [role="tab"][aria-selected="true"]' in source
    assert "focus-visible" in source
    assert "font-family:Inter" in source


def test_search_guidance_is_help_not_repeated_caption() -> None:
    source = (ROOT / "dashboard" / "research_ui.py").read_text(encoding="utf-8")

    assert '"filter_mode": "fuzzy"' in source
    assert '"help": "Start typing to filter options."' in source
    assert 'st.caption("Open the list and start typing to filter options.")' not in source


def test_owner_home_uses_dashboard_scale_hero() -> None:
    source = (ROOT / "dashboard" / "app.py").read_text(encoding="utf-8")

    assert "clamp(2.15rem,3.3vw,3.45rem)" in source


def test_fantasy_decision_feed_is_top_three_card_first() -> None:
    source = (
        ROOT / "dashboard" / "pages" / "11_Fantasy_HQ.py"
    ).read_text(encoding="utf-8")

    assert "weekly_feed.actions[:3]" in source
    assert 'with st.container(border=True):' in source
    assert 'f"All ranked actions · {len(feed_rows)}"' in source
