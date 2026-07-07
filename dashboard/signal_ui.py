from __future__ import annotations

from pathlib import Path
from typing import Iterable

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
    return load_csv_safe(path)


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


def filter_multiselect(df: pd.DataFrame, column: str, label: str) -> pd.DataFrame:
    if df.empty or column not in df.columns:
        return df
    options = sorted(value for value in df[column].dropna().astype(str).unique() if value)
    selected = st.multiselect(label, options)
    return df if not selected else df[df[column].astype(str).isin(selected)]


def filter_minimum(df: pd.DataFrame, column: str, label: str, default: float = 0.0) -> pd.DataFrame:
    if df.empty or column not in df.columns:
        return df
    values = pd.to_numeric(df[column], errors="coerce")
    max_value = float(values.max()) if values.notna().any() else default
    threshold = st.slider(label, min_value=0.0, max_value=max(max_value, default), value=default)
    return df[values.fillna(-1) >= threshold]


def top_signal_cards(df: pd.DataFrame, count: int = 5) -> None:
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
                  <div class="metric-help" style="margin-top:.45rem;">{row.get('top_signal_reason', '')}</div>
                  <div class="metric-help">{row.get('review_reason', '')}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
