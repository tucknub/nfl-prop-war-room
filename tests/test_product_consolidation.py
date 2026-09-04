from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_owner_navigation_is_collapsed_to_four_core_workspaces() -> None:
    app = (ROOT / "dashboard" / "app.py").read_text(encoding="utf-8")

    assert '"PropWar": [' in app
    assert 'title="Today"' in app
    assert 'title="Players"' in app
    assert 'title="Markets"' in app
    assert 'title="Fantasy"' in app

    owner_core = app[app.index('"PropWar": [') : app.index('"More": [')]
    assert 'url_path=""' in owner_core
    assert 'url_path="players"' in owner_core
    assert 'url_path="glitch-radar"' in owner_core
    assert 'url_path="fantasy-hq"' in owner_core

    for title in (
        "Teams",
        "Reports",
        "Games",
        "Advanced Research",
        "Market Research",
        "Methodology",
    ):
        assert f'title="{title}"' in app

    assert 'title="Margin"' in app
    assert 'title="Knockout"' in app


def test_owner_home_is_decision_first_not_report_first() -> None:
    app = (ROOT / "dashboard" / "app.py").read_text(encoding="utf-8")

    assert "NFL DECISION INTELLIGENCE · PRIVATE BETA" in app
    assert "<h1>What matters right now?</h1>" in app
    assert '"Core workspaces"' not in app
    assert '"Players"' in app
    assert '"Markets"' in app
    assert '"Fantasy"' in app
    assert "render_propwar_today_if_owner()" in app
    assert "Use the top navigation for Players, Markets, and Fantasy." in app


def test_markets_and_market_research_have_product_level_headings() -> None:
    markets = (
        ROOT / "dashboard" / "pages" / "09_Glitch_Radar.py"
    ).read_text(encoding="utf-8")
    research = (
        ROOT / "dashboard" / "pages" / "10_Deep_Prop_Radar.py"
    ).read_text(encoding="utf-8")

    assert 'st.markdown("## Markets")' in markets
    assert "ParlayAPI market preview" in markets
    assert "every displayed price must be verified in the sportsbook" in markets
    assert 'st.markdown("## Market Research")' in research
    assert "Advanced market research" in research
    assert "quotes 120 seconds old or newer" in research


def test_repository_has_one_authoritative_product_definition() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    product = (ROOT / "PRODUCT.md").read_text(encoding="utf-8")

    assert readme.startswith("# PropWar\n")
    assert "See **[PRODUCT.md](PRODUCT.md)**" in readme
    assert "Legacy research-engine documentation" in readme

    assert "PropWar has four primary owner workspaces." in product
    for heading in ("### 1. Today", "### 2. Players", "### 3. Markets", "### 4. Fantasy"):
        assert heading in product
    assert "Product freeze" in product
    assert "Phase 1 — finish on Streamlit" in product
    assert "Phase 2 — Cloudflare product shell" in product
