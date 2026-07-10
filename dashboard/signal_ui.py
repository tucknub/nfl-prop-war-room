from __future__ import annotations

from pathlib import Path
from typing import Iterable
from html import escape

import pandas as pd
import streamlit as st

from utils import load_csv_safe, metric_card, section_header


TIER_COLORS = {
    "ELITE_SIGNAL": "#0b6b3a",
    "STRONG_SIGNAL": "#16803f",
    "GOOD_SIGNAL": "#2ea44f",
    "WATCH": "#b08900",
    "REVIEW": "#c96a17",
    "BLOCKED": "#b42318",
    "INSUFFICIENT_DATA": "#667085",
}

STATUS_COLORS = {
    "READY": "#0b6b3a",
    "PASS": "#16803f",
    "GO": "#0b6b3a",
    "WATCH": "#b08900",
    "NEEDS DATA": "#667085",
    "NEEDS REVIEW": "#c96a17",
    "REVIEW": "#c96a17",
    "NO-GO": "#b42318",
    "BLOCKED": "#b42318",
    "FAIL": "#b42318",
    "HISTORICAL TEST ONLY": "#2563eb",
    "DATA_NEEDS_LIVE_CONTEXT": "#667085",
}


def load_signal_csv(path: str | Path) -> pd.DataFrame:
    return clean_display_frame(load_csv_safe(path))


def clean_display_text(value: object, fallback: str = "—") -> str:
    """Return presentation-safe copy without changing the underlying data."""
    if value is None or pd.isna(value):
        return fallback
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "nat", "<na>"}:
        return fallback
    return text


def clean_display_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Sanitize display-only text values for bettor-facing tables and cards."""
    if df is None or df.empty:
        return df
    view = df.copy()
    missing_tokens = {"", "nan", "none", "null", "nat", "<na>"}
    for column in view.columns:
        if pd.api.types.is_object_dtype(view[column]) or pd.api.types.is_string_dtype(view[column]):
            view[column] = view[column].map(
                lambda value: pd.NA
                if value is None or (isinstance(value, str) and value.strip().lower() in missing_tokens)
                else value
            )
            view[column] = view[column].replace(
                {
                    "HISTORICAL TEST ONLY": "Research mode",
                    "NOT_AVAILABLE": "Unavailable",
                    "NEEDS SOURCE": "Unavailable",
                }
            )
    fallbacks = {
        "player_name": "Player unavailable",
        "team": "Team TBD",
        "opponent": "Opponent TBD",
        "position": "Position TBD",
    }
    for column, fallback in fallbacks.items():
        if column in view.columns:
            view[column] = view[column].fillna(fallback)
    return view


def player_selection_token(row: pd.Series) -> str:
    player_id = clean_display_text(row.get("player_id"), "")
    if player_id:
        return f"id::{player_id}"
    return "name::{player}|{team}|{position}".format(
        player=clean_display_text(row.get("player_name"), ""),
        team=clean_display_text(row.get("team"), ""),
        position=clean_display_text(row.get("position"), ""),
    )


def render_player_detail_action(row: pd.Series, key: str) -> None:
    """Open Player Details with this card's player selected when available."""
    if st.button("View player details →", key=key, use_container_width=True):
        st.session_state["player_detail_key"] = player_selection_token(row)
        st.switch_page("pages/04_Player_Signal_Drilldown.py")


def inject_signal_css() -> None:
    st.markdown(
        """
        <style>
        .signal-shell {
          background: linear-gradient(180deg, #f8fafc 0%, #eef3f8 100%);
          border: 1px solid #d7dee8;
          border-radius: 18px;
          box-shadow: 0 18px 46px rgba(15, 23, 42, .12);
          padding: 1.15rem;
          margin: 1rem 0;
        }
        .signal-header {
          background: linear-gradient(135deg, #0b1628 0%, #17243a 58%, #26364d 100%);
          border: 1px solid rgba(255,255,255,.1);
          border-radius: 18px;
          padding: 1.2rem 1.3rem;
          box-shadow: 0 20px 48px rgba(0,0,0,.28);
          margin: .5rem 0 1rem;
        }
        .signal-header h2 { color: #f8fafc; margin: 0 0 .35rem; letter-spacing: 0; }
        .signal-header p { color: #c8d3e2; margin: 0; }
        .signal-kpi-card {
          background: #ffffff;
          border: 1px solid #d8e0ea;
          border-radius: 10px;
          box-shadow: 0 2px 8px rgba(15, 23, 42, .07);
          padding: .95rem;
          min-height: 118px;
        }
        .signal-kpi-title { color: #526172; font-size: .75rem; font-weight: 900; text-transform: uppercase; }
        .signal-kpi-value { color: #111827; font-size: 1.55rem; font-weight: 950; line-height: 1.05; margin: .38rem 0; }
        .signal-kpi-subtitle { color: #6b7280; font-size: .82rem; }
        .signal-player-card {
          background: #ffffff;
          border: 1px solid #d8e0ea;
          border-radius: 10px;
          padding: 1rem;
          box-shadow: 0 2px 8px rgba(15, 23, 42, .07);
          min-height: 150px;
        }
        .signal-player-card .name { color: #0f172a; font-weight: 950; font-size: 1.05rem; }
        .signal-player-card .meta { color: #64748b; font-size: .82rem; margin: .18rem 0 .65rem; }
        .signal-player-card .score { color: #0b6b3a; font-size: 1.7rem; font-weight: 950; line-height: 1; }
        .signal-spotlight-card {
          background: #ffffff;
          border: 1px solid #d8e0ea;
          border-radius: 10px;
          padding: .8rem .85rem;
          box-shadow: 0 2px 8px rgba(15, 23, 42, .07);
          min-height: 142px;
        }
        .signal-spotlight-card .rank { color: #64748b; font-size: .72rem; font-weight: 900; text-transform: uppercase; }
        .signal-spotlight-card .name { color: #0f172a; font-size: 1.08rem; font-weight: 950; margin: .15rem 0; word-break: keep-all; overflow-wrap: normal; }
        .signal-spotlight-card .meta { color: #64748b; font-size: .82rem; }
        .signal-spotlight-card .score { color: #0b6b3a; font-size: 1.85rem; font-weight: 950; line-height: 1; margin: .55rem 0; }
        .signal-spotlight-card .reason { color: #475569; font-size: .82rem; line-height: 1.3; margin-top: .45rem; }
        .plain-signal-list {
          background: #ffffff;
          border: 1px solid #d8e0ea;
          border-radius: 12px;
          padding: .8rem .95rem;
          margin: .5rem 0;
          box-shadow: 0 10px 24px rgba(15, 23, 42, .08);
        }
        .plain-signal-list h4 { color: #0f172a; margin: 0 0 .45rem; }
        .plain-signal-list ul { color: #334155; margin: .35rem 0 .1rem 1.1rem; padding: 0; }
        .plain-signal-list li { margin: .18rem 0; }
        .signal-pill {
          display: inline-flex;
          align-items: center;
          gap: .25rem;
          padding: .22rem .58rem;
          border-radius: 999px;
          font-size: .73rem;
          font-weight: 900;
          border: 1px solid transparent;
          white-space: nowrap;
          word-break: keep-all;
          margin: .1rem .18rem .1rem 0;
        }
        .pill-green-dark { color: #eafff1; background: #064e2f; border-color: #0b6b3a; }
        .pill-green { color: #f1fff6; background: #16803f; border-color: #1f9d55; }
        .pill-green-light { color: #0f3f26; background: #bcf7cf; border-color: #6ee7a0; }
        .pill-yellow { color: #3d310d; background: #ffe199; border-color: #d9a441; }
        .pill-orange { color: #fff4e6; background: #c96a17; border-color: #e08b31; }
        .pill-red { color: #fff2f2; background: #b42318; border-color: #e15245; }
        .pill-gray { color: #e5e7eb; background: #667085; border-color: #98a2b3; }
        .pill-blue { color: #eff6ff; background: #2563eb; border-color: #60a5fa; }
        .signal-chip-row { display: flex; flex-wrap: wrap; gap: .4rem; margin: .45rem 0 .75rem; }
        .signal-legend { display:flex;flex-wrap:wrap;gap:.45rem;margin:.35rem 0 .8rem; }
        @media (max-width: 640px) {
          .signal-spotlight-card {
            min-height: 0;
            padding: .65rem .7rem;
          }
          .signal-spotlight-card .name { font-size: .98rem; }
          .signal-spotlight-card .score { font-size: 1.55rem; margin: .35rem 0; }
          .signal-spotlight-card .reason { display: none; }
          .signal-spotlight-card + div[data-testid="stButton"] button {
            min-height: 2rem;
            padding: .25rem .5rem;
            font-size: .78rem;
          }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _pill_class(value: object, kind: str = "status") -> str:
    text = "" if pd.isna(value) else str(value).upper()
    if kind == "score":
        score = pd.to_numeric(value, errors="coerce")
        if pd.isna(score):
            return "pill-gray"
        if score >= 85:
            return "pill-green-dark"
        if score >= 70:
            return "pill-green"
        if score >= 55:
            return "pill-yellow"
        if score >= 40:
            return "pill-orange"
        return "pill-red"
    if text in {"ELITE_SIGNAL", "PRIORITY_REVIEW"}:
        return "pill-green-dark"
    if text in {"STRONG_SIGNAL", "READY", "PASS", "GO"}:
        return "pill-green"
    if text in {"GOOD_SIGNAL", "HIGH"}:
        return "pill-green-light"
    if text in {"WATCH", "WATCHLIST", "HISTORICAL TEST ONLY", "MEDIUM"}:
        return "pill-yellow"
    if text in {"REVIEW", "REVIEW_CONTEXT", "LOW_PRIORITY", "NEEDS REVIEW", "CHECK", "LOW"}:
        return "pill-orange"
    if text in {"BLOCKED", "BLOCKED_DATA", "FAIL", "NO-GO", "DO NOT USE"}:
        return "pill-red"
    if "MISSING" in text or "NEEDS" in text or "NOT_AVAILABLE" in text or not text:
        return "pill-gray"
    return "pill-blue"


def _pill(value: object, kind: str = "status") -> str:
    text = "NOT_AVAILABLE" if pd.isna(value) or str(value).strip() == "" else str(value)
    return f"<span class='signal-pill {_pill_class(value, kind)}'>{escape(text)}</span>"


def render_signal_badge(value: object) -> str:
    number = pd.to_numeric(value, errors="coerce")
    return _pill(value, "score" if pd.notna(number) else "status")


def render_action_badge(value: object) -> str:
    return _pill(value, "action")


def render_reliability_badge(value: object) -> str:
    return _pill(value, "reliability")


def render_metric_chip(label: str, value: object, status: object | None = None) -> None:
    st.markdown(
        f"<span class='signal-pill {_pill_class(status if status is not None else value)}'><strong>{escape(label)}:</strong> {escape(str(value))}</span>",
        unsafe_allow_html=True,
    )


def section_label(text: str) -> None:
    st.markdown(
        f"""
        <div style="display:inline-block;margin:.15rem 0 .65rem;padding:.22rem .6rem;border-radius:999px;
        border:1px solid #334155;background:#111827;color:#9fb3cc;font-size:.76rem;font-weight:900;">
        Section: {text}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_pill(section_name: str) -> None:
    section_label(section_name)


def render_status_banner(text: str, status: object) -> None:
    st.markdown(
        f"""
        <div class="signal-header">
          <h2>{escape(str(status))}</h2>
          <p>{escape(str(text))}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def command_center_card(title: str, value: object, status: object | None = None, help_text: str | None = None) -> None:
    status_html = _pill(status) if status is not None else ""
    subtitle = f"<div class='signal-kpi-subtitle'>{escape(str(help_text))}</div>" if help_text else ""
    st.markdown(
        f"""
        <div class="signal-kpi-card">
          <div class="signal-kpi-title">{escape(str(title))}</div>
          <div class="signal-kpi-value">{escape(str(value))}</div>
          {status_html}
          {subtitle}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_card(title: str, value: object, subtitle: str | None = None, status: object | None = None) -> None:
    command_center_card(title, value, status, subtitle)


def render_player_signal_card(row: pd.Series) -> None:
    score = row.get("overall_signal_score", row.get("challenger_overall_signal_score", "n/a"))
    st.markdown(
        f"""
        <div class="signal-player-card">
          <div class="name">{escape(clean_display_text(row.get('player_name'), 'Player unavailable'))}</div>
          <div class="meta">{escape(clean_display_text(row.get('team'), 'Team TBD'))} vs {escape(clean_display_text(row.get('opponent'), 'Opponent TBD'))} / {escape(clean_display_text(row.get('position'), 'Position TBD'))}</div>
          <div class="score">{format_percent_or_score(score)}</div>
          <div>{_pill(row.get('signal_tier', row.get('challenger_signal_tier', '')))}</div>
          <div class="metric-help">{escape(str(row.get('top_signal_reason', row.get('preview_notes', '')) or ''))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def summarize_reason(value: object, max_len: int = 110) -> str:
    if pd.isna(value):
        return ""
    text = str(value).replace("Context V1:", "").replace("NOT_AVAILABLE", "missing").strip()
    while "  " in text:
        text = text.replace("  ", " ")
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rsplit(" ", 1)[0] + "..."


def render_spotlight_card(row: pd.Series, rank: int | None = None, action_key: str | None = None) -> None:
    score = format_percent_or_score(row.get("overall_signal_score"))
    rank_text = f"#{rank} Slate Spotlight" if rank else "Slate Spotlight"
    reason = summarize_reason(row.get("top_signal_reason", row.get("signal_explanation", "")))
    st.markdown(
        f"""
        <div class="signal-spotlight-card">
          <div class="rank">{escape(rank_text)}</div>
          <div class="name">{escape(clean_display_text(row.get('player_name'), 'Player unavailable'))}</div>
          <div class="meta">{escape(clean_display_text(row.get('team'), 'Team TBD'))} vs {escape(clean_display_text(row.get('opponent'), 'Opponent TBD'))} / {escape(clean_display_text(row.get('position'), 'Position TBD'))}</div>
          <div class="score">{escape(score)}</div>
          <div>{_pill(row.get('signal_tier', ''))}</div>
          <div class="reason">{escape(reason)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if action_key:
        render_player_detail_action(row, action_key)


def quick_link_card(title: str, description: str, page_name: str) -> None:
    st.markdown(
        f"""
        <div class="info-card">
          <div class="player-name">{title}</div>
          <div class="player-meta">{page_name}</div>
          <div class="metric-help">{description}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_signal_legend() -> None:
    st.markdown(
        """
        <div class="signal-legend">
          <span class="signal-pill pill-green-dark">Dark green = elite</span>
          <span class="signal-pill pill-green">Green = strong</span>
          <span class="signal-pill pill-yellow">Yellow = watch</span>
          <span class="signal-pill pill-orange">Orange = review/risk</span>
          <span class="signal-pill pill-red">Red = blocked/weak</span>
          <span class="signal-pill pill-gray">Gray = missing/unavailable</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def score_color(value: object) -> str:
    score = pd.to_numeric(value, errors="coerce")
    if pd.isna(score):
        return "background-color: #3f4652; color: #e5e7eb;"
    score = float(score)
    if score >= 85:
        return "background-color: #0b6b3a; color: white; font-weight: 800;"
    if score >= 70:
        return "background-color: #16803f; color: white; font-weight: 750;"
    if score >= 55:
        return "background-color: #f2c94c; color: #111827; font-weight: 750;"
    if score >= 40:
        return "background-color: #f2994a; color: #111827; font-weight: 750;"
    return "background-color: #b42318; color: white; font-weight: 750;"


def _badge(value: object, colors: dict[str, str]) -> str:
    text = "MISSING" if pd.isna(value) else str(value)
    color = colors.get(text.upper(), "#2563eb")
    return f"<span style='display:inline-block;border-radius:999px;padding:.18rem .55rem;background:{color};color:white;font-weight:850;font-size:.75rem'>{text}</span>"


def tier_badge(tier: object) -> str:
    return _badge(tier, TIER_COLORS)


def readiness_badge(value: object) -> str:
    return _badge(value, STATUS_COLORS)


def status_badge(value: object) -> str:
    return readiness_badge(value)


def format_percent_or_score(value: object) -> str:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return "n/a"
    number = float(number)
    if 0 <= number <= 1:
        return f"{number:.1%}"
    return f"{number:.1f}"


def status_color(value: object) -> str:
    text = "" if pd.isna(value) else str(value).upper()
    if text in {"READY", "PASS", "GO", "ELITE_SIGNAL", "STRONG_SIGNAL", "GOOD_SIGNAL"}:
        return "background-color: #103d26; color: #c8f7d6; font-weight: 750;"
    if text in {"WATCH", "HISTORICAL TEST ONLY"}:
        return "background-color: #3d310d; color: #ffe199; font-weight: 750;"
    if "REVIEW" in text:
        return "background-color: #4a2b0f; color: #ffd9a8; font-weight: 750;"
    if text in {"NO-GO", "BLOCKED", "FAIL"}:
        return "background-color: #451717; color: #ffb4b4; font-weight: 750;"
    if "NEEDS" in text or "MISSING" in text or "NOT_AVAILABLE" in text:
        return "background-color: #2f3744; color: #d0d5dd; font-weight: 750;"
    return ""


def build_heatmap_styler(df: pd.DataFrame, score_columns: Iterable[str], status_columns: Iterable[str] | None = None):
    display = df.copy()
    score_columns = [col for col in score_columns if col in display.columns]
    status_columns = [col for col in (status_columns or []) if col in display.columns]
    styler = display.style
    if score_columns:
        styler = styler.map(score_color, subset=score_columns)
        styler = styler.format({col: format_percent_or_score for col in score_columns})
    if status_columns:
        styler = styler.map(status_color, subset=status_columns)
    return styler


def build_signal_heatmap(df: pd.DataFrame, score_columns: Iterable[str], status_columns: Iterable[str] | None = None):
    return build_heatmap_styler(df, score_columns, status_columns)


def safe_display_dataframe(df: pd.DataFrame, height: int = 600) -> None:
    if df is None or df.empty:
        st.info("No rows available for this view.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True, height=height)


def render_signal_kpis(df: pd.DataFrame) -> None:
    tiers = df["signal_tier"].astype(str) if not df.empty and "signal_tier" in df.columns else pd.Series(dtype=str)
    score = pd.to_numeric(df.get("overall_signal_score", pd.Series(dtype=float)), errors="coerce")
    cols = st.columns(5)
    with cols[0]:
        metric_card("Rows", len(df), "PASS" if len(df) else "MISSING")
    with cols[1]:
        metric_card("Elite/Strong/Good", int(tiers.isin(["ELITE_SIGNAL", "STRONG_SIGNAL", "GOOD_SIGNAL"]).sum()), "GOOD_SIGNAL")
    with cols[2]:
        metric_card("Review/Blocked", int(tiers.isin(["REVIEW", "BLOCKED", "INSUFFICIENT_DATA"]).sum()), "REVIEW")
    with cols[3]:
        metric_card("Avg Score", f"{score.mean():.1f}" if score.notna().any() else "n/a", "INFO")
    with cols[4]:
        missing = pd.to_numeric(df.get("missing_signal_count", pd.Series(dtype=float)), errors="coerce").fillna(0)
        metric_card("Missing Signals", int(missing.sum()), "NEEDS SOURCE")


def render_signal_table(
    df: pd.DataFrame,
    score_columns: list[str],
    display_columns: list[str],
    title: str,
    help_text: str | None = None,
) -> None:
    section_header(title, help_text)
    if df.empty:
        st.info("No rows available for this view.")
        return
    columns = [col for col in display_columns if col in df.columns]
    view = df[columns].copy()
    status_columns = [col for col in ["signal_tier", "roster_status", "role_status", "injury_status", "readiness_status"] if col in view.columns]
    st.dataframe(build_heatmap_styler(view, score_columns, status_columns), use_container_width=True, hide_index=True)


def filter_multiselect(df: pd.DataFrame, column: str, label: str, key: str | None = None) -> pd.DataFrame:
    if df.empty or column not in df.columns:
        return df
    options = sorted(value for value in df[column].dropna().astype(str).unique() if value)
    selected = st.multiselect(label, options, key=key)
    return df if not selected else df[df[column].astype(str).isin(selected)]


def filter_minimum(df: pd.DataFrame, column: str, label: str, default: float = 0.0, key: str | None = None) -> pd.DataFrame:
    if df.empty or column not in df.columns:
        return df
    values = pd.to_numeric(df[column], errors="coerce")
    finite_values = values.replace([float("inf"), float("-inf")], pd.NA).dropna()
    if finite_values.empty:
        st.caption(f"{label}: no numeric values available.")
        return df
    max_value = float(finite_values.max())
    min_value = 0.0
    if max_value <= min_value:
        st.caption(f"{label}: all available values are {max_value:.1f}.")
        return df
    threshold_default = min(max(float(default), min_value), max_value)
    threshold = st.slider(label, min_value=min_value, max_value=max_value, value=threshold_default, key=key)
    return df[values.fillna(-1) >= threshold]


def top_signal_cards(df: pd.DataFrame, count: int = 5, action_key_prefix: str = "top_signal") -> None:
    if df.empty:
        return
    view = df.sort_values("overall_signal_score", ascending=False).head(count)
    cols = st.columns(min(count, max(1, len(view))))
    for idx, (_, row) in enumerate(view.iterrows()):
        with cols[idx % len(cols)]:
            st.markdown(
                f"""
                <div class="player-card">
                  <div class="player-name">{row.get('player_name', '')}</div>
                  <div class="player-meta">{row.get('team', '')} / {row.get('opponent', '')} / {row.get('position', '')}</div>
                  <div class="player-proj">{format_percent_or_score(row.get('overall_signal_score'))}</div>
                  <div>{tier_badge(row.get('signal_tier'))}</div>
                  <div class="metric-help" style="margin-top:.45rem;">{summarize_reason(row.get('top_signal_reason', ''))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            render_player_detail_action(row, f"{action_key_prefix}_{idx}_{player_selection_token(row)}")
