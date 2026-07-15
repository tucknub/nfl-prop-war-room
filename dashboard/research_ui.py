from __future__ import annotations

from html import escape
from typing import Iterable
from urllib.parse import quote

import numpy as np
import pandas as pd
import streamlit as st

from research_data import percent, pp


PUBLIC_SOURCE_NOTE = "Historical regular-season role and opportunity data through 2025."


def configure_page(title: str) -> None:
    st.set_page_config(page_title=f"{title} | PropWar", page_icon="PW", layout="wide")
    inject_styles()


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
          --pw-ink:#071d37; --pw-ink-2:#0c2a4d; --pw-blue:#0b5cff;
          --pw-text:#10233d; --pw-muted:#5f6f82; --pw-line:#d9e0e8;
          --pw-soft:#f4f7fb; --pw-white:#fff; --pw-warn:#895f00;
        }
        html, body, [class*="css"] { font-family:Inter,"Segoe UI",Arial,sans-serif; color:var(--pw-text); }
        .stApp { background:var(--pw-white); }
        #MainMenu, [data-testid="stDecoration"], [data-testid="stStatusWidget"] { display:none !important; }
        [data-testid="stHeader"] { background:rgba(255,255,255,.98); height:2.8rem; }
        [data-testid="stSidebar"] { background:linear-gradient(180deg,var(--pw-ink) 0%,#062545 100%); border-right:1px solid #16395f; }
        [data-testid="stSidebar"] * { color:#f8fbff; }
        [data-testid="stSidebarNav"] { padding-top:.65rem; }
        [data-testid="stSidebarNav"] a { border-radius:0; min-height:2.65rem; border-left:3px solid transparent; }
        [data-testid="stSidebarNav"] a[aria-current="page"] { background:rgba(255,255,255,.08); border-left-color:var(--pw-blue); }
        [data-testid="stSidebarNav"] a:hover { background:rgba(255,255,255,.06); }
        .block-container { max-width:1480px; padding-top:4.25rem; padding-bottom:6rem; }
        h1,h2,h3 { font-family:"Arial Narrow","Segoe UI",Arial,sans-serif; color:var(--pw-ink)!important; letter-spacing:-.03em; }
        .pw-intro h1 { font-size:clamp(2.05rem,3.1vw,3.35rem)!important; font-weight:800; line-height:1.02!important; margin:0 0 .3rem!important; padding:0!important; }
        h2 { font-size:1.4rem; font-weight:760; margin-top:1.3rem; }
        h3 { font-size:1rem; font-weight:750; letter-spacing:-.01em; }
        p,label,button,input,[data-baseweb="select"] { font-size:.91rem; }
        [data-testid="stSelectbox"] label,[data-testid="stTextInput"] label,[data-testid="stMultiSelect"] label,
        [data-testid="stSlider"] label,[data-testid="stNumberInput"] label,[data-testid="stSegmentedControl"] label {
          color:#44556b; font-size:.72rem; font-weight:700; text-transform:uppercase; letter-spacing:.04em;
        }
        [data-baseweb="select"] > div { min-height:2.55rem; }
        .pw-brand { margin:.15rem 0 .8rem; }
        .pw-brand strong { display:block; font-size:1.55rem; letter-spacing:-.05em; }
        .pw-brand span { color:#9fc0e8; font-size:.69rem; letter-spacing:.07em; }
        .pw-intro { display:flex; align-items:flex-end; justify-content:space-between; gap:1.5rem; padding-bottom:.65rem; border-bottom:1px solid var(--pw-line); margin-bottom:.65rem; }
        .pw-intro p { max-width:720px; color:var(--pw-muted); font-size:.94rem; margin:.18rem 0 0; line-height:1.45; }
        .pw-season-note { color:var(--pw-muted); font-size:.76rem; white-space:nowrap; padding-bottom:.2rem; }
        .pw-section { display:flex; align-items:baseline; gap:.55rem; margin:1.15rem 0 .45rem; border-bottom:1px solid var(--pw-line); }
        .pw-section h2 { margin:0 0 .35rem; padding:0!important; }
        .pw-section span { color:var(--pw-muted); font-size:.79rem; }
        .pw-note { border-left:3px solid var(--pw-blue); background:var(--pw-soft); padding:.6rem .75rem; color:#40536a; font-size:.81rem; margin:.45rem 0 .7rem; }
        .pw-note.amber { border-left-color:#d99200; }
        .pw-source { border-top:1px solid var(--pw-line); margin-top:1.4rem; padding-top:.6rem; display:flex; justify-content:space-between; gap:1rem; color:var(--pw-muted); font-size:.72rem; }
        .pw-filter-summary { border:1px solid var(--pw-line); border-radius:10px; margin:.45rem 0 .35rem; overflow:hidden; background:#fff; }
        .pw-filter-line { padding:.58rem .75rem; color:var(--pw-ink); font-size:.88rem; font-weight:700; }
        .pw-filter-line + .pw-filter-line { border-top:1px solid var(--pw-line); color:#40536a; font-weight:600; }
        .pw-filter-sample { color:var(--pw-muted); font-size:.76rem; font-weight:500; margin-left:.35rem; }
        [data-testid="stExpander"] { border:1px solid var(--pw-line); border-radius:8px; box-shadow:none; }
        [data-testid="stExpander"] summary { min-height:2.7rem; font-weight:700; color:var(--pw-blue); }
        .pw-overview { display:grid; grid-template-columns:1.35fr repeat(3,1fr); border:1px solid #cbd9ef; border-radius:10px; background:#f7faff; margin:.65rem 0 .8rem; }
        .pw-overview > div { padding:.7rem .8rem; border-right:1px solid #dce6f5; }
        .pw-overview > div:last-child { border-right:0; }
        .pw-overview span { display:block; color:var(--pw-muted); font-size:.69rem; text-transform:uppercase; letter-spacing:.035em; }
        .pw-overview strong { display:block; margin-top:.12rem; color:var(--pw-ink); font-size:1rem; font-variant-numeric:tabular-nums; }
        .pw-change-list { border-top:1px solid var(--pw-line); }
        .pw-change-row { display:grid; grid-template-columns:minmax(170px,1.3fr) repeat(5,minmax(86px,.65fr)) minmax(210px,1.35fr); gap:12px; align-items:center; padding:.8rem .35rem .8rem .85rem; border-bottom:1px solid var(--pw-line); position:relative; }
        .pw-change-row:before { content:""; position:absolute; left:0; top:9px; bottom:9px; width:3px; background:var(--pw-blue); }
        .pw-player { font-weight:760; color:var(--pw-ink); }
        .pw-meta,.pw-cell small { display:block; color:var(--pw-muted); font-size:.72rem; margin-top:.12rem; }
        .pw-cell { font-variant-numeric:tabular-nums; font-weight:680; color:var(--pw-text); }
        .pw-cell .pw-label { display:block; text-transform:uppercase; letter-spacing:.035em; font-size:.63rem; color:var(--pw-muted); font-weight:700; margin-bottom:.12rem; }
        .pw-delta { color:var(--pw-blue); }
        .pw-factual { font-size:.8rem; line-height:1.35; font-weight:500; }
        .pw-mobile-only { display:none; }
        [class*="st-key-mobile_full_"] { display:none; }
        .pw-card-list { display:grid; gap:.62rem; margin:.55rem 0; }
        .pw-card { border:1px solid var(--pw-line); border-radius:10px; background:#fff; overflow:hidden; }
        .pw-card-head { display:flex; justify-content:space-between; gap:.6rem; padding:.72rem .75rem .55rem; }
        .pw-card-title { color:var(--pw-ink); font-size:.98rem; font-weight:780; }
        .pw-card-subtitle { color:var(--pw-muted); font-size:.74rem; margin-top:.08rem; }
        .pw-card-rank { color:var(--pw-blue); font-size:.78rem; font-weight:800; white-space:nowrap; }
        .pw-card-metrics { border-top:1px solid var(--pw-line); }
        .pw-card-metric { display:grid; grid-template-columns:1fr auto; gap:.7rem; align-items:center; padding:.52rem .75rem; border-bottom:1px solid #e8edf3; }
        .pw-card-metric:last-child { border-bottom:0; }
        .pw-card-label { color:#32465e; font-size:.79rem; font-weight:660; }
        .pw-card-detail { display:block; color:var(--pw-muted); font-size:.68rem; margin-top:.04rem; font-weight:500; }
        .pw-card-value { color:var(--pw-ink); font-size:.84rem; font-weight:760; font-variant-numeric:tabular-nums; text-align:right; }
        .pw-card-value.accent { color:var(--pw-blue); }
        .pw-card-note { padding:.5rem .75rem; color:#4b5e73; background:var(--pw-soft); font-size:.72rem; line-height:1.35; }
        .pw-card-actions { display:flex; align-items:center; justify-content:space-between; gap:.5rem; padding:.52rem .75rem; border-top:1px solid var(--pw-line); }
        .pw-card-link { color:var(--pw-blue)!important; text-decoration:none!important; font-size:.78rem; font-weight:760; }
        .pw-card details { width:100%; }
        .pw-card details summary { cursor:pointer; color:var(--pw-blue); font-size:.77rem; font-weight:740; }
        .pw-card details p { color:#40536a; font-size:.72rem; line-height:1.4; margin:.45rem 0 0; }
        .pw-kpis { display:grid; grid-template-columns:repeat(4,1fr); border:1px solid var(--pw-line); border-radius:10px; margin:.6rem 0 .75rem; overflow:hidden; }
        .pw-kpi { padding:.68rem .75rem; border-right:1px solid var(--pw-line); }
        .pw-kpi:last-child { border-right:0; }
        .pw-kpi span { display:block; color:var(--pw-muted); font-size:.66rem; text-transform:uppercase; letter-spacing:.035em; }
        .pw-kpi strong { display:block; color:var(--pw-ink); font-size:1.08rem; margin-top:.1rem; font-variant-numeric:tabular-nums; }
        .pw-kpi small { display:block; color:var(--pw-muted); font-size:.66rem; margin-top:.05rem; }
        .pw-conditions { border:1px solid var(--pw-line); border-radius:8px; padding:.7rem .8rem; margin:.55rem 0 .7rem; }
        .pw-conditions p { margin:.16rem 0; color:#40536a; font-size:.79rem; }
        [data-testid="stDataFrame"] { border:1px solid var(--pw-line); border-radius:6px; }
        [data-testid="stDataFrame"] * { font-size:.8rem; font-variant-numeric:tabular-nums; }
        [data-testid="stMetric"] { border-left:2px solid var(--pw-blue); padding-left:.65rem; }
        .stButton>button,.stDownloadButton>button { border-radius:6px; border:1px solid var(--pw-blue); color:var(--pw-blue); font-weight:700; min-height:2.4rem; }
        .stButton>button[kind="primary"] { background:var(--pw-blue); color:#fff; }
        [data-testid="stSegmentedControl"] button { min-height:2.45rem; font-size:.8rem; }
        [data-testid="stVegaLiteChart"] { overflow:hidden; }
        @media (max-width:900px) {
          .block-container { padding:4.1rem .8rem 6rem; }
          .pw-intro h1 { font-size:2rem!important; line-height:1.04!important; }
          .pw-intro { display:block; margin-bottom:.45rem; padding-bottom:.5rem; }
          .pw-intro p { font-size:.86rem; line-height:1.38; max-width:38rem; }
          .pw-season-note { margin-top:.3rem; white-space:normal; font-size:.7rem; }
          .pw-section { display:block; margin:.9rem 0 .35rem; }
          .pw-section h2 { font-size:1.2rem; margin-bottom:.1rem; }
          .pw-section span { display:block; padding-bottom:.3rem; line-height:1.3; }
          .pw-overview { grid-template-columns:1fr 1fr; }
          .pw-overview>div { border-bottom:1px solid #dce6f5; }
          .pw-overview>div:nth-child(2) { border-right:0; }
          .pw-overview>div:nth-last-child(-n+2) { border-bottom:0; }
          .pw-change-row { grid-template-columns:1fr 1fr; gap:.55rem .85rem; padding:.7rem .25rem .7rem .75rem; }
          .pw-change-row>.pw-factual { grid-column:1/-1; }
          .pw-kpis { grid-template-columns:1fr 1fr; }
          .pw-kpi:nth-child(2) { border-right:0; }
          .pw-kpi:nth-child(-n+2) { border-bottom:1px solid var(--pw-line); }
        }
        @media (max-width:520px) {
          [data-testid="stHeader"] { height:2.35rem; }
          .block-container { padding:2.55rem .72rem 7rem; }
          .pw-intro h1 { font-size:1.82rem!important; line-height:1.06!important; max-width:100%; }
          .pw-intro p { font-size:.82rem; margin-top:.12rem; }
          .pw-mobile-only { display:block; }
          [class*="st-key-mobile_full_"] { display:block; }
          [class*="st-key-desktop_"] { display:none!important; }
          .pw-change-list { display:none; }
          .pw-filter-line { padding:.5rem .65rem; font-size:.82rem; }
          .pw-filter-sample { display:block; margin:.15rem 0 0; }
          [data-testid="stExpander"] summary { min-height:2.45rem; font-size:.84rem; }
          [data-testid="stHorizontalBlock"] { flex-wrap:wrap; gap:.45rem; }
          [data-testid="column"] { min-width:145px!important; flex:1 1 145px!important; }
          .pw-overview>div { padding:.56rem .62rem; }
          .pw-overview strong { font-size:.9rem; }
          .pw-card-head { padding:.62rem .65rem .48rem; }
          .pw-card-metric { padding:.46rem .65rem; }
          .pw-card-note,.pw-card-actions { padding:.46rem .65rem; }
          .pw-kpi { padding:.56rem .62rem; }
          .pw-source { display:block; line-height:1.45; }
          [data-testid="stVegaLiteChart"] { margin-left:-.25rem; margin-right:-.25rem; }
          [data-testid="stSidebarCollapsedControl"] button { width:2.4rem; height:2.4rem; }
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
    return None


def note(text: str, amber: bool = False) -> None:
    klass = "pw-note amber" if amber else "pw-note"
    st.markdown(f'<div class="{klass}">{escape(text)}</div>', unsafe_allow_html=True)


def source_footer(extra: str = "") -> None:
    st.markdown(
        f'<div class="pw-source"><span>{escape(PUBLIC_SOURCE_NOTE)}</span><span>{escape(extra)}</span></div>',
        unsafe_allow_html=True,
    )


def selection_summary_text(primary: str, secondary: str = "", sample: str = "") -> str:
    return " | ".join(part for part in [primary, secondary, sample] if part)


def selection_summary(primary: str, secondary: str = "", sample: str = "", *, target=None) -> None:
    secondary_html = f'<div class="pw-filter-line">{escape(secondary)}' if secondary else ""
    if secondary:
        if sample:
            secondary_html += f'<span class="pw-filter-sample">{escape(sample)}</span>'
        secondary_html += "</div>"
    html = f'<div class="pw-filter-summary"><div class="pw-filter-line">{escape(primary)}</div>{secondary_html}</div>'
    (target or st).markdown(html, unsafe_allow_html=True)


def overview(items: Iterable[tuple[str, str]]) -> None:
    st.markdown(
        '<div class="pw-overview">' + "".join(
            f'<div><span>{escape(label)}</span><strong>{escape(value)}</strong></div>' for label, value in items
        ) + "</div>",
        unsafe_allow_html=True,
    )


def ratio_text(raw: object, denominator: object, noun: str = "opportunities") -> str:
    if pd.isna(raw) or pd.isna(denominator) or float(denominator) <= 0:
        return "—"
    raw_int, den_int = int(float(raw)), int(float(denominator))
    return f"{raw_int} of {den_int} {noun} · {100 * raw_int / den_int:.1f}%"


def role_noun(role_family: str) -> str:
    return {
        "rb_carry_share": "carries",
        "rb_opportunity_share": "RB opportunities",
        "wr_target_share": "targets",
        "te_target_share": "targets",
    }.get(role_family, "opportunities")


def numeric_percent(frame: pd.DataFrame, source: str, destination: str) -> pd.DataFrame:
    result = frame.copy()
    result[destination] = pd.to_numeric(result[source], errors="coerce") * 100.0
    return result


def numeric_percent_sort(frame: pd.DataFrame, column: str, *, ascending: bool = False) -> pd.DataFrame:
    result = frame.copy()
    result[column] = pd.to_numeric(result[column], errors="coerce")
    return result.sort_values(column, ascending=ascending, na_position="last", kind="stable").reset_index(drop=True)


def nfl_week_axis_values() -> list[int]:
    return list(range(1, 19))


def resolve_query_choice(
    options: list[object],
    requested: object | None,
    session_value: object | None = None,
) -> tuple[object | None, bool]:
    """Resolve URL state before widget state, returning an explicit invalid flag."""
    if requested not in {None, ""}:
        return (requested, False) if requested in options else (None, True)
    if session_value in options:
        return session_value, False
    return (options[0], False) if options else (None, False)


def player_href(player_id: object, season: int, role_family: str) -> str:
    return f"/players?player={quote(str(player_id))}&season={season}&family={quote(role_family)}"


def render_mobile_cards(cards: list[dict[str, object]]) -> None:
    if not cards:
        return
    html = ['<div class="pw-mobile-only"><div class="pw-card-list">']
    for card in cards:
        rank = f'<span class="pw-card-rank">{escape(str(card.get("rank", "")))}</span>' if card.get("rank") else ""
        html.append(
            '<article class="pw-card"><div class="pw-card-head"><div>'
            f'<div class="pw-card-title">{escape(str(card.get("title", "")))}</div>'
            f'<div class="pw-card-subtitle">{escape(str(card.get("subtitle", "")))}</div></div>{rank}</div>'
        )
        metrics = card.get("metrics", [])
        if metrics:
            html.append('<div class="pw-card-metrics">')
            for metric in metrics:
                label, value = str(metric[0]), str(metric[1])
                detail = str(metric[2]) if len(metric) > 2 and metric[2] else ""
                accent = " accent" if len(metric) > 3 and bool(metric[3]) else ""
                html.append(
                    '<div class="pw-card-metric"><div class="pw-card-label">'
                    f'{escape(label)}{f"<span class=\"pw-card-detail\">{escape(detail)}</span>" if detail else ""}</div>'
                    f'<div class="pw-card-value{accent}">{escape(value)}</div></div>'
                )
            html.append("</div>")
        if card.get("note"):
            html.append(f'<div class="pw-card-note">{escape(str(card["note"]))}</div>')
        href = card.get("href")
        details = card.get("details")
        if href or details:
            html.append('<div class="pw-card-actions">')
            if details:
                html.append(
                    f'<details><summary>View details</summary><p>{escape(str(details))}</p></details>'
                )
            if href:
                html.append(f'<a class="pw-card-link" href="{escape(str(href))}" target="_self">Open player →</a>')
            html.append("</div>")
        html.append("</article>")
    html.append("</div></div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def render_change_rows(frame: pd.DataFrame, limit: int = 10) -> None:
    if frame.empty:
        st.info("No rows match this season and week.")
        return
    cards: list[dict[str, object]] = []
    for rank, (_, row) in enumerate(frame.head(limit).iterrows(), start=1):
        noun = role_noun(str(row["role_family"]))
        cards.append(
            {
                "rank": f"#{rank}",
                "title": str(row["player_name"]),
                "subtitle": f"{row['team']} · {row['position']} · {row['role_family_label']}",
                "metrics": [
                    ("Share change", f"{percent(row['baseline_share'])} → {percent(row['recent_share'])}", pp(row["change"]), True),
                    ("Recent usage", ratio_text(row["raw_opportunities"], row["team_denominator"], noun), "Normal game"),
                    ("Baseline sample", f"{int(row['baseline_games'])} games", "Prior qualifying games"),
                ],
                "note": str(row["partial_game_note"]) if "Suspected" in str(row["partial_game_note"]) else "",
                "details": f"Normal game {percent(row['metric_normal'])}; all play {percent(row['metric_all'])}. {row['factual_text']}",
                "href": player_href(row["player_id"], int(row["season"]), str(row["role_family"])),
            }
        )
    render_mobile_cards(cards)

    html = ['<div class="pw-change-list">']
    for _, row in frame.head(limit).iterrows():
        html.append(
            '<div class="pw-change-row">'
            f'<div><span class="pw-player">{escape(str(row["player_name"]))}</span>'
            f'<span class="pw-meta">{escape(str(row["team"]))} · {escape(str(row["position"]))} · {escape(str(row["role_family_label"]))}</span></div>'
            f'<div class="pw-cell"><span class="pw-label">Prior</span>{percent(row["baseline_share"])}</div>'
            f'<div class="pw-cell pw-delta"><span class="pw-label">Recent</span>{percent(row["recent_share"])}<small>{pp(row["change"])}</small></div>'
            f'<div class="pw-cell"><span class="pw-label">Count</span>{int(row["raw_opportunities"])} / {int(row["team_denominator"])}</div>'
            f'<div class="pw-cell"><span class="pw-label">Context</span>Normal game</div>'
            f'<div class="pw-cell"><span class="pw-label">Sample</span>{int(row["baseline_games"])} games</div>'
            f'<div class="pw-factual">{escape(str(row["factual_text"]))}</div></div>'
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def condition_box(conditions: str, baseline: str, sample: str) -> None:
    st.markdown(
        f'<div class="pw-conditions"><p><strong>Conditions:</strong> {escape(conditions)}</p>'
        f'<p><strong>Comparison:</strong> {escape(baseline)}</p><p><strong>Sample:</strong> {escape(sample)}</p></div>',
        unsafe_allow_html=True,
    )


def kpi_row(items: list[tuple[str, str] | tuple[str, str, str]]) -> None:
    st.markdown(
        '<div class="pw-kpis">' + "".join(
            f'<div class="pw-kpi"><span>{escape(str(item[0]))}</span><strong>{escape(str(item[1]))}</strong>'
            f'{f"<small>{escape(str(item[2]))}</small>" if len(item) > 2 else ""}</div>' for item in items
        ) + "</div>",
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


def responsive_table(
    frame: pd.DataFrame,
    cards: list[dict[str, object]],
    *,
    key: str,
    height: int = 440,
    percent_columns: list[str] | None = None,
    label: str = "View full table",
) -> None:
    render_mobile_cards(cards)
    with st.container(key=f"desktop_{key}"):
        table(frame, height=height, percent_columns=percent_columns)
    with st.container(key=f"mobile_full_{key}"):
        with st.expander(label):
            table(frame, height=min(height, 420), percent_columns=percent_columns)


def methodology_expander(lines: Iterable[str]) -> None:
    with st.expander("How this is calculated"):
        for line in lines:
            st.markdown(f"- {line}")
