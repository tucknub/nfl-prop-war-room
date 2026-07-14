from __future__ import annotations

from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

from research_data import percent, pp


PUBLIC_SOURCE_NOTE = (
    "Canonical player-week-role data: audited regular seasons 2018–2025. "
    "Confirmed partial games are excluded; suspected partial games remain visible and included."
)


def configure_page(title: str) -> None:
    st.set_page_config(page_title=f"{title} | PropWar", page_icon="PW", layout="wide")
    inject_styles()


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
          --pw-ink: #071d37;
          --pw-ink-2: #0c2a4d;
          --pw-blue: #0b5cff;
          --pw-coral: #f04f4f;
          --pw-amber: #d99200;
          --pw-text: #10233d;
          --pw-muted: #5f6f82;
          --pw-line: #d9e0e8;
          --pw-soft: #f4f7fb;
          --pw-white: #ffffff;
        }
        html, body, [class*="css"] { font-family: Inter, "Segoe UI", Arial, sans-serif; color: var(--pw-text); }
        .stApp { background: var(--pw-white); }
        [data-testid="stHeader"] { background: rgba(255,255,255,.96); }
        [data-testid="stSidebar"] { background: linear-gradient(180deg, var(--pw-ink) 0%, #062545 100%); border-right: 1px solid #16395f; }
        [data-testid="stSidebar"] * { color: #f8fbff; }
        [data-testid="stSidebarNav"] { padding-top: 1.25rem; }
        [data-testid="stSidebarNav"] a { border-radius: 0; min-height: 2.85rem; border-left: 3px solid transparent; }
        [data-testid="stSidebarNav"] a[aria-current="page"] { background: rgba(255,255,255,.08); border-left-color: var(--pw-blue); }
        [data-testid="stSidebarNav"] a:hover { background: rgba(255,255,255,.06); }
        .block-container { max-width: 1480px; padding-top: 2rem; padding-bottom: 3rem; }
        h1, h2, h3 { font-family: "Arial Narrow", "Segoe UI", Arial, sans-serif; color: var(--pw-ink) !important; letter-spacing: -0.035em; }
        h1 { font-size: clamp(2.1rem, 3.4vw, 3.55rem); font-weight: 800; line-height: 1.02; margin: 0 0 .4rem 0; }
        h2 { font-size: 1.55rem; font-weight: 760; margin-top: 1.7rem; }
        h3 { font-size: 1.05rem; font-weight: 750; letter-spacing: -.01em; }
        p, label, button, input, [data-baseweb="select"] { font-size: .93rem; }
        [data-testid="stSelectbox"] label, [data-testid="stTextInput"] label,
        [data-testid="stMultiSelect"] label, [data-testid="stSlider"] label,
        [data-testid="stNumberInput"] label { color: #44556b; font-size: .76rem; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; }
        .pw-brand { margin: .25rem 0 1.2rem; }
        .pw-brand strong { display:block; font-size:1.65rem; letter-spacing:-.05em; }
        .pw-brand span { color:#9fc0e8; font-size:.73rem; letter-spacing:.07em; }
        .pw-intro { display:flex; align-items:flex-end; justify-content:space-between; gap:2rem; padding-bottom:1rem; border-bottom:1px solid var(--pw-line); margin-bottom:1.1rem; }
        .pw-intro p { max-width: 760px; color:var(--pw-muted); font-size:1rem; margin:.25rem 0 0; }
        .pw-season-note { color:var(--pw-muted); font-size:.78rem; white-space:nowrap; padding-bottom:.35rem; }
        .pw-section { display:flex; align-items:baseline; gap:.7rem; margin:1.65rem 0 .65rem; border-bottom:1px solid var(--pw-line); }
        .pw-section h2 { margin:0 0 .45rem; }
        .pw-section span { color:var(--pw-muted); font-size:.82rem; }
        .pw-yard-rule { height:20px; margin: .4rem 0 .8rem; border-top:1px solid #b7c3d1; background:repeating-linear-gradient(90deg, transparent 0, transparent 18px, #c5cfda 19px, transparent 20px); background-size:20px 7px; background-repeat:repeat-x; }
        .pw-note { border-left:3px solid var(--pw-blue); background:var(--pw-soft); padding:.7rem .9rem; color:#40536a; font-size:.84rem; margin:.6rem 0 1rem; }
        .pw-note.amber { border-left-color:var(--pw-amber); }
        .pw-source { border-top:1px solid var(--pw-ink); margin-top:2rem; padding-top:.7rem; display:flex; justify-content:space-between; gap:1rem; color:var(--pw-muted); font-size:.74rem; }
        .pw-change-list { border-top:1px solid var(--pw-line); }
        .pw-change-row { display:grid; grid-template-columns:minmax(190px,1.4fr) repeat(6,minmax(88px,.65fr)) minmax(230px,1.5fr); gap:14px; align-items:center; padding:1rem .4rem 1rem 1rem; border-bottom:1px solid var(--pw-line); position:relative; color:var(--pw-text); }
        .pw-change-row:before { content:""; position:absolute; left:0; top:10px; bottom:10px; width:3px; background:var(--pw-blue); }
        .pw-change-row.down:before { background:var(--pw-coral); }
        .pw-player { font-weight:750; color:var(--pw-blue); }
        .pw-change-row.down .pw-player, .pw-change-row.down .pw-delta { color:var(--pw-coral); }
        .pw-meta, .pw-cell small { display:block; color:var(--pw-muted); font-size:.75rem; margin-top:.18rem; }
        .pw-cell { font-variant-numeric:tabular-nums; font-weight:650; color:var(--pw-text); }
        .pw-cell .pw-label { display:block; text-transform:uppercase; letter-spacing:.035em; font-size:.66rem; color:var(--pw-muted); font-weight:700; margin-bottom:.16rem; }
        .pw-delta { color:var(--pw-blue); }
        .pw-factual { font-size:.84rem; line-height:1.35; font-weight:500; }
        .pw-team-rail { display:grid; grid-template-columns:repeat(8,minmax(80px,1fr)); border:1px solid var(--pw-line); }
        .pw-team { padding:.8rem; text-align:center; font-weight:780; color:var(--pw-ink); border-right:1px solid var(--pw-line); }
        .pw-team:last-child { border-right:0; }
        .pw-conditions { border:1px solid var(--pw-line); padding:1rem; margin:.7rem 0 1rem; }
        .pw-conditions strong { color:var(--pw-ink); }
        .pw-conditions p { margin:.25rem 0; color:#40536a; font-size:.84rem; }
        .pw-kpis { display:grid; grid-template-columns:repeat(4,1fr); border-top:1px solid var(--pw-line); border-bottom:1px solid var(--pw-line); margin: .8rem 0 1rem; }
        .pw-kpi { padding:.85rem 1rem; border-right:1px solid var(--pw-line); }
        .pw-kpi:last-child { border-right:0; }
        .pw-kpi span { display:block; color:var(--pw-muted); font-size:.7rem; text-transform:uppercase; letter-spacing:.04em; }
        .pw-kpi strong { display:block; color:var(--pw-ink); font-size:1.25rem; margin-top:.15rem; font-variant-numeric:tabular-nums; }
        [data-testid="stDataFrame"] { border:1px solid var(--pw-line); border-radius:0; }
        [data-testid="stDataFrame"] * { font-size:.82rem; font-variant-numeric:tabular-nums; }
        [data-testid="stMetric"] { border-left:2px solid var(--pw-blue); padding-left:.75rem; }
        .stButton > button, .stDownloadButton > button { border-radius:4px; border:1px solid var(--pw-blue); color:var(--pw-blue); font-weight:700; }
        .stButton > button[kind="primary"] { background:var(--pw-blue); color:white; }
        [data-baseweb="tab-list"] { border-bottom:1px solid var(--pw-line); gap:1.2rem; }
        [data-baseweb="tab"] { border-radius:0; padding-left:0; padding-right:0; font-weight:650; }
        [data-baseweb="tab"][aria-selected="true"] { color:var(--pw-blue); }
        .stAlert { border-radius:4px; }
        @media (max-width: 1400px) {
          .pw-change-row { grid-template-columns:minmax(180px,1.25fr) repeat(3,minmax(90px,.7fr)); }
          .pw-change-row > .pw-factual { grid-column:1/-1; }
        }
        @media (max-width: 900px) {
          .block-container { padding:1.1rem .9rem 5rem; }
          h1 { font-size:2.15rem; }
          .pw-intro { display:block; }
          .pw-season-note { margin-top:.6rem; white-space:normal; }
          .pw-change-row { grid-template-columns:1fr 1fr; gap:.7rem 1rem; padding:1rem .25rem 1rem .9rem; }
          .pw-change-row > .pw-factual { grid-column:1/-1; }
          .pw-team-rail { grid-template-columns:repeat(4,1fr); }
          .pw-team { border-bottom:1px solid var(--pw-line); }
          .pw-kpis { grid-template-columns:1fr 1fr; }
          .pw-kpi:nth-child(2) { border-right:0; }
        }
        @media (max-width: 520px) {
          .pw-change-row { grid-template-columns:1fr; }
          .pw-change-row > .pw-factual { grid-column:auto; }
          .pw-team-rail { grid-template-columns:repeat(2,1fr); }
          .pw-source { display:block; }
          [data-testid="stHorizontalBlock"] { flex-wrap:wrap; }
          [data-testid="column"] { min-width:100% !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def sidebar_brand() -> None:
    with st.sidebar:
        st.markdown(
            '<div class="pw-brand"><strong>PropWar</strong><span>NFL ROLE &amp; USAGE RESEARCH</span></div>',
            unsafe_allow_html=True,
        )


def page_intro(title: str, description: str, latest_season: int = 2025) -> None:
    st.markdown(
        f'<div class="pw-intro"><div><h1>{escape(title)}</h1><p>{escape(description)}</p></div>'
        f'<div class="pw-season-note">Latest completed season: <strong>{latest_season}</strong></div></div>',
        unsafe_allow_html=True,
    )


def section(title: str, subtitle: str = "") -> None:
    st.markdown(
        f'<div class="pw-section"><h2>{escape(title)}</h2><span>{escape(subtitle)}</span></div>',
        unsafe_allow_html=True,
    )


def yard_rule() -> None:
    st.markdown('<div class="pw-yard-rule"></div>', unsafe_allow_html=True)


def note(text: str, amber: bool = False) -> None:
    klass = "pw-note amber" if amber else "pw-note"
    st.markdown(f'<div class="{klass}">{escape(text)}</div>', unsafe_allow_html=True)


def source_footer(extra: str = "") -> None:
    st.markdown(
        f'<div class="pw-source"><span>{escape(PUBLIC_SOURCE_NOTE)}</span><span>{escape(extra)}</span></div>',
        unsafe_allow_html=True,
    )


def render_change_rows(frame: pd.DataFrame, limit: int = 5) -> None:
    if frame.empty:
        st.info("No rows match this season and week.")
        return
    html = ['<div class="pw-change-list">']
    for _, row in frame.head(limit).iterrows():
        direction = "down" if float(row["change"]) < 0 else "up"
        html.append(
            f'<div class="pw-change-row {direction}">'
            f'<div><span class="pw-player">{escape(str(row["player_name"]))}</span>'
            f'<span class="pw-meta">{escape(str(row["team"]))} · {escape(str(row["role_family_label"]))}</span></div>'
            f'<div class="pw-cell"><span class="pw-label">Prior baseline</span>{percent(row["baseline_share"])}</div>'
            f'<div class="pw-cell pw-delta"><span class="pw-label">Recent game</span>{percent(row["recent_share"])}<small>{pp(row["change"])}</small></div>'
            f'<div class="pw-cell"><span class="pw-label">Opportunities</span>{int(row["raw_opportunities"])} / {int(row["team_denominator"])}</div>'
            f'<div class="pw-cell"><span class="pw-label">Normal game</span>{percent(row["metric_normal"])}</div>'
            f'<div class="pw-cell"><span class="pw-label">All play</span>{percent(row["metric_all"])}</div>'
            f'<div class="pw-cell"><span class="pw-label">Baseline</span>{int(row["baseline_games"])} games</div>'
            f'<div class="pw-factual">{escape(str(row["factual_text"]))}<span class="pw-meta">{escape(str(row["partial_game_note"]))}</span></div>'
            '</div>'
        )
    html.append('</div>')
    st.markdown("".join(html), unsafe_allow_html=True)


def team_rail(teams: list[str]) -> None:
    st.markdown(
        '<div class="pw-team-rail">' + "".join(f'<div class="pw-team">{escape(team)}</div>' for team in teams[:8]) + '</div>',
        unsafe_allow_html=True,
    )


def condition_box(conditions: str, baseline: str, sample: str) -> None:
    st.markdown(
        f'<div class="pw-conditions"><p><strong>Conditions:</strong> {escape(conditions)}</p>'
        f'<p><strong>Baseline:</strong> {escape(baseline)}</p><p><strong>Sample:</strong> {escape(sample)}</p></div>',
        unsafe_allow_html=True,
    )


def kpi_row(items: list[tuple[str, str]]) -> None:
    st.markdown(
        '<div class="pw-kpis">' + "".join(
            f'<div class="pw-kpi"><span>{escape(label)}</span><strong>{escape(value)}</strong></div>'
            for label, value in items
        ) + '</div>',
        unsafe_allow_html=True,
    )


def table(frame: pd.DataFrame, *, height: int = 440, percent_columns: list[str] | None = None) -> None:
    if frame.empty:
        st.info("No rows match the current filters.")
        return
    config: dict[str, object] = {}
    for column in percent_columns or []:
        if column in frame:
            config[column] = st.column_config.NumberColumn(column, format="%.1f%%")
    st.dataframe(frame, width="stretch", hide_index=True, height=height, column_config=config)
