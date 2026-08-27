from pathlib import Path


PAGE = (
    Path(__file__).resolve().parents[1]
    / "dashboard"
    / "pages"
    / "11_Fantasy_HQ.py"
)


def _source() -> str:
    return PAGE.read_text(encoding="utf-8")


def test_fantasy_hq_search_tools_are_fragment_isolated():
    source = _source()

    for helper in (
        "_render_available_player_search",
        "_render_player_market_map",
        "_render_cross_league_player_lookup",
    ):
        assert f"def {helper}" in source

    assert source.count("@st.fragment") >= 3
    assert "_render_available_player_search(league, all_catalog, all_states)" in source
    assert "_render_player_market_map(league, all_states, all_catalog)" in source
    assert "_render_cross_league_player_lookup(catalog, all_states)" in source


def test_player_market_search_requires_submit_before_heavy_work():
    source = _source()

    assert "fantasy_hq_player_market_search_form" in source
    assert "st.form_submit_button(" in source
    assert '"Search player market"' in source
    assert "fantasy_hq_player_market_submitted_query" in source
