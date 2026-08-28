from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import quote

import streamlit as st


DASHBOARD_DIR = Path(__file__).resolve().parent
REPO_ROOT = DASHBOARD_DIR.parent
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from access_control import access_mode  # noqa: E402
from research_ui import inject_styles, section  # noqa: E402
from research_data import operational_status_text  # noqa: E402
from public_copy import role_home_copy  # noqa: E402
from home_page import render_home  # noqa: E402
from propwar_today_owner import render_propwar_today_if_owner  # noqa: E402


REPORT_CARDS = (
    ("Backfield Control", "See which running backs own their team's carries and total backfield opportunities."),
    ("Target Hierarchy", "See how documented WR and TE targets are distributed within each offense."),
    ("Role Movement", "See which player roles gained or lost the most share versus the prior period."),
)


def _secrets_snapshot() -> dict:
    try:
        return dict(st.secrets.to_dict()) if hasattr(st.secrets, "to_dict") else dict(st.secrets)
    except Exception:
        return {}


def _user_snapshot() -> dict:
    try:
        return dict(st.user.to_dict()) if hasattr(st.user, "to_dict") else dict(st.user)
    except Exception:
        return {}


def inject_usability_styles() -> None:
    st.markdown(
        """
        <style>
        footer, #viewerBadge_link, [data-testid="stAppDeployButton"] { display:none !important; }
        [data-testid="stHeader"] {
          display:flex !important;
          visibility:visible !important;
          opacity:1 !important;
          background:rgba(255,255,255,.98) !important;
        }
        [data-testid="stToolbar"], [data-testid="stHeaderActionElements"] {
          visibility:visible !important;
          opacity:1 !important;
        }
        .pw-home-hero { max-width:920px; margin:.15rem 0 .65rem; }
        .pw-home-hero>span { display:block; color:var(--pw-blue); font-size:.72rem; font-weight:800; letter-spacing:.075em; margin-bottom:.45rem; }
        .pw-home-hero h1 { font-size:clamp(2.3rem,4vw,4.2rem)!important; font-weight:820; line-height:.98!important; margin:0 0 .6rem!important; padding:0!important; }
        .pw-home-hero p { max-width:760px; color:var(--pw-muted); font-size:1.02rem; line-height:1.5; margin:0; }
        .pw-status-line { display:flex; align-items:flex-start; gap:.7rem; padding:.62rem .75rem; border:1px solid #cbd9ef; border-radius:8px; background:#f7faff; margin:.75rem 0 .9rem; }
        .pw-status-line strong { color:var(--pw-ink); font-size:.78rem; white-space:nowrap; }
        .pw-status-line span { color:#40536a; font-size:.79rem; line-height:1.4; }
        .pw-primary-link { display:flex; align-items:center; justify-content:center; min-height:2.45rem; padding:.45rem .75rem; border:1px solid var(--pw-blue); border-radius:6px; background:var(--pw-blue); color:#fff!important; font-size:.86rem; font-weight:760; text-decoration:none!important; text-align:center; }
        .pw-primary-link:hover { background:#074edb; border-color:#074edb; }
        .pw-overview strong { line-height:1.25!important; white-space:normal!important; overflow-wrap:anywhere!important; }
        @media (max-width:900px) {
          .pw-home-hero h1 { font-size:2.55rem!important; line-height:1.02!important; }
          .pw-home-hero p { font-size:.92rem; }
        }
        @media (max-width:520px) {
          .pw-home-hero { margin-top:.05rem; }
          .pw-home-hero>span { font-size:.64rem; margin-bottom:.35rem; }
          .pw-home-hero h1 { font-size:2.08rem!important; line-height:1.02!important; }
          .pw-home-hero p { font-size:.84rem; line-height:1.4; }
          .pw-status-line { display:block; padding:.55rem .62rem; }
          .pw-status-line strong { display:block; margin-bottom:.12rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_launch_home() -> None:
    mode = access_mode(_secrets_snapshot(), _user_snapshot())
    if mode == "OWNER":
        st.markdown(
            """
            <section class="pw-home-hero">
              <span>PROP WAR · NFL DECISION INTELLIGENCE · PRIVATE BETA</span>
              <h1>What matters right now?</h1>
              <p>PropWar combines player role changes, live market structure, fantasy decisions, and specialized league tools into one owner workflow.</p>
            </section>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="pw-status-line"><strong>Role data</strong><span>{operational_status_text()}</span></div>',
            unsafe_allow_html=True,
        )
        render_propwar_today_if_owner()

        section(
            "Core workspaces",
            "Four places define PropWar now. Everything else is supporting evidence or a specialized owner tool.",
        )
        quick_columns = st.columns(3)
        quick_cards = (
            (
                "Players",
                "Search one player and connect role change, live market context, fantasy ownership, and exposure.",
                "/players",
            ),
            (
                "Markets",
                "See the strongest current pricing anomalies, movement, line shopping, and market structure.",
                "/glitch-radar",
            ),
            (
                "Fantasy",
                "Get lineup, waiver, trade, manager, and cross-league decisions from Fantasy HQ.",
                "/fantasy-hq",
            ),
        )
        for column, (title, description, href) in zip(quick_columns, quick_cards):
            with column:
                with st.container(border=True):
                    st.markdown(f"### {title}")
                    st.write(description)
                    st.markdown(
                        f'<a class="pw-primary-link" href="{href}">Open {title}</a>',
                        unsafe_allow_html=True,
                    )
        st.caption(
            "Supporting team/game reports, advanced research, Margin, Knockout, and deeper market diagnostics live under More."
        )
        return

    copy = role_home_copy()
    st.markdown(
        f"""
        <section class="pw-home-hero">
          <span>PROP WAR · NFL ROLE INTELLIGENCE · PUBLIC BETA</span>
          <h1>{copy['hero_title']}</h1>
          <p>{copy['hero_description']}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="pw-status-line"><strong>Data status</strong><span>{operational_status_text()}</span></div>',
        unsafe_allow_html=True,
    )

    section("Choose a report", "Each report answers one documented role question without market or outcome claims.")
    report_columns = st.columns(3)
    for column, (title, description) in zip(report_columns, REPORT_CARDS):
        with column:
            with st.container(border=True):
                st.markdown(f"### {title}")
                st.write(description)
                st.markdown(
                    f'<a class="pw-primary-link" href="/reports?report={quote(title)}">View {title}</a>',
                    unsafe_allow_html=True,
                )
    st.caption("Historical and current-season role research only. Every percentage remains attached to its player count and team total.")
    st.divider()
    render_home()


def _render_owner_auth(mode: str, user: dict) -> None:
    _, auth_col = st.columns([8.5, 1.5], vertical_alignment="center")
    with auth_col:
        if mode == "AUTH_UNAVAILABLE":
            st.caption("Owner tools unavailable")
            return
        label = "Owner ✓" if mode == "OWNER" else "Owner"
        with st.popover(label, width="stretch"):
            if mode == "ANONYMOUS":
                st.caption("Personal tools are hidden until owner sign-in.")
                if st.button("Owner sign in", key="owner_login", width="stretch"):
                    st.login()
            elif mode == "OWNER":
                email = str(user.get("email") or "Owner")
                st.caption(f"Owner mode · {email}")
                if st.button("Sign out", key="owner_logout", width="stretch"):
                    st.logout()
            elif mode == "NON_OWNER":
                st.caption("Signed in · public access only")
                if st.button("Sign out", key="non_owner_logout", width="stretch"):
                    st.logout()


def main() -> None:
    st.set_page_config(
        page_title="PropWar",
        page_icon="PW",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    inject_styles()
    inject_usability_styles()

    secrets = _secrets_snapshot()
    user = _user_snapshot()
    mode = access_mode(secrets, user)

    role_pages = [
        st.Page(render_launch_home, title="Home", icon=":material/home:", url_path="", default=True),
        st.Page("pages/04_Reports.py", title="Reports", icon=":material/bar_chart:", url_path="reports"),
        st.Page("pages/01_Teams.py", title="Teams", icon=":material/groups:", url_path="teams"),
        st.Page("pages/02_Players.py", title="Players", icon=":material/person_search:", url_path="players"),
        st.Page("pages/03_Games.py", title="Games", icon=":material/sports_football:", url_path="games"),
        st.Page("pages/05_Explorer.py", title="Advanced Research", icon=":material/search:", url_path="explorer"),
        st.Page("pages/06_Methodology.py", title="Methodology", icon=":material/menu_book:", url_path="methodology"),
    ]
    pages: dict[str, list] = {"Role Intelligence": role_pages}

    if mode == "OWNER":
        pages = {
            "PropWar": [
                st.Page(render_launch_home, title="Today", icon=":material/home:", url_path="", default=True),
                st.Page("pages/02_Players.py", title="Players", icon=":material/person_search:", url_path="players"),
                st.Page("pages/09_Glitch_Radar.py", title="Markets", icon=":material/radar:", url_path="glitch-radar"),
                st.Page("pages/11_Fantasy_HQ.py", title="Fantasy", icon=":material/sports_esports:", url_path="fantasy-hq"),
            ],
            "More": [
                st.Page("pages/01_Teams.py", title="Teams", icon=":material/groups:", url_path="teams"),
                st.Page("pages/04_Reports.py", title="Reports", icon=":material/bar_chart:", url_path="reports"),
                st.Page("pages/03_Games.py", title="Games", icon=":material/sports_football:", url_path="games"),
                st.Page("pages/05_Explorer.py", title="Advanced Research", icon=":material/search:", url_path="explorer"),
                st.Page("pages/10_Deep_Prop_Radar.py", title="Market Research", icon=":material/query_stats:", url_path="deep-prop-radar"),
                st.Page("pages/07_Margin_War_Room.py", title="Margin War Room", icon=":material/trophy:", url_path="margin"),
                st.Page("pages/08_Knockout_Fantasy_War_Room.py", title="Knockout Fantasy", icon=":material/bolt:", url_path="knockout"),
                st.Page("pages/06_Methodology.py", title="Methodology", icon=":material/menu_book:", url_path="methodology"),
            ],
        }

    _render_owner_auth(mode, user)
    st.navigation(pages, position="top").run()


if __name__ == "__main__":
    main()
