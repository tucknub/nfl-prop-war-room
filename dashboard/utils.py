from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd
import streamlit as st


READY_STATUSES = {"GO", "READY", "PASS", "HIGH", "TRUE"}
WARN_STATUSES = {"NEEDS DATA", "REVIEW", "CHECK", "WARNING", "MEDIUM", "HISTORICAL TEST ONLY"}
BAD_STATUSES = {"NO-GO", "BLOCKED", "NOT READY", "FAIL", "LOW", "DO NOT USE", "TEAM_VERIFY", "FALSE"}

DISPLAY_NAMES = {
    "player": "Player",
    "player_name": "Player",
    "team": "Team",
    "opponent": "Opponent",
    "position": "Pos",
    "line": "Line",
    "raw_projection": "Raw Projection",
    "projected_receptions_raw": "Raw Projection",
    "calibrated_projection": "Calibrated Projection",
    "projected_receptions_calibrated": "Calibrated Projection",
    "model_over_probability": "Model Over Probability",
    "model_under_probability": "Model Under Probability",
    "usage_status": "Usage Status",
    "confidence_tier": "Confidence",
    "confidence_bucket": "Confidence",
    "quality_flags": "Flags",
    "flags": "Flags",
}


def find_repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        if (parent / "config.yaml").exists() and (parent / "src").exists():
            return parent
    return Path.cwd()


def resolve_path(path: str | Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return find_repo_root() / path


@st.cache_data(show_spinner=False)
def load_csv_safe(path: str | Path) -> pd.DataFrame:
    resolved = resolve_path(path)
    if not resolved.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(resolved, low_memory=False)
    except Exception as exc:  # pragma: no cover - surfaced in dashboard
        st.error(f"Could not read {resolved}: {exc}")
        return pd.DataFrame()


@st.cache_data(show_spinner=False)
def load_markdown_safe(path: str | Path) -> str:
    resolved = resolve_path(path)
    if not resolved.exists():
        return ""
    try:
        return resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return resolved.read_text(errors="replace")
    except Exception as exc:  # pragma: no cover - surfaced in dashboard
        st.error(f"Could not read {resolved}: {exc}")
        return ""


def status_level(status: object) -> str:
    text = str(status).strip().upper()
    if text in READY_STATUSES:
        return "good"
    if text in BAD_STATUSES or "NO-GO" in text or "FAIL" in text or "BLOCK" in text:
        return "bad"
    if text in WARN_STATUSES or "NEEDS" in text or "HISTORICAL" in text:
        return "warn"
    return "neutral"


def status_pill(status: object) -> str:
    text = "UNKNOWN" if pd.isna(status) else str(status)
    level = status_level(text)
    return f"<span class='status-pill {level}'>{text}</span>"


def status_badge(status: object) -> str:
    return status_pill(status)


def format_percent(value: object) -> str:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return "n/a"
    return f"{float(number):.1%}"


def get_latest_mtime(paths: Iterable[str | Path]) -> datetime | None:
    mtimes = []
    for path in paths:
        resolved = resolve_path(path)
        if resolved.exists():
            mtimes.append(resolved.stat().st_mtime)
    if not mtimes:
        return None
    return datetime.fromtimestamp(max(mtimes))


def value_from_status(check_name: str, default: str = "UNKNOWN") -> str:
    status = load_csv_safe("outputs/run_reports/latest_receptions_pipeline_status.csv")
    if status.empty or "check_name" not in status.columns or "value" not in status.columns:
        return default
    row = status[status["check_name"].astype(str).eq(check_name)]
    if row.empty:
        return default
    value = row["value"].iloc[0]
    return default if pd.isna(value) else str(value)


def show_missing(path: str | Path) -> None:
    st.warning(f"Missing file: `{resolve_path(path)}`")


def show_table_or_missing(df: pd.DataFrame, path: str | Path, **kwargs) -> None:
    if df.empty and not resolve_path(path).exists():
        show_missing(path)
        return
    st.dataframe(df, use_container_width=True, hide_index=True, **kwargs)


def coalesce_column(df: pd.DataFrame, candidates: list[str], fallback: str) -> pd.Series:
    for col in candidates:
        if col in df.columns:
            return df[col]
    return pd.Series([fallback] * len(df), index=df.index)


def first_existing_columns(df: pd.DataFrame, candidates: list[str]) -> list[str]:
    return [col for col in candidates if col in df.columns]


def numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(df[column], errors="coerce")


def filter_by_multiselect(df: pd.DataFrame, column: str, label: str) -> pd.DataFrame:
    if df.empty or column not in df.columns:
        return df
    values = sorted(v for v in df[column].dropna().astype(str).unique() if v)
    selected = st.multiselect(label, values)
    if not selected:
        return df
    return df[df[column].astype(str).isin(selected)]


def filter_by_search(df: pd.DataFrame, column: str, label: str = "Player search") -> pd.DataFrame:
    if df.empty or column not in df.columns:
        return df
    query = st.text_input(label).strip().lower()
    if not query:
        return df
    return df[df[column].astype(str).str.lower().str.contains(query, na=False)]


def metric_card(label: str, value: object, status: object | None = None, help_text: str | None = None) -> None:
    status_html = status_pill(status) if status is not None else ""
    helper = f"<div class='metric-help'>{help_text}</div>" if help_text else ""
    st.markdown(
        f"""
        <div class="metric-card">
          <div class="metric-label">{label}</div>
          <div class="metric-value">{value}</div>
          {status_html}
          {helper}
        </div>
        """,
        unsafe_allow_html=True,
    )


def warning_banner(title: str, body: str) -> None:
    st.markdown(
        f"""
        <div class="warning-banner">
          <div class="warning-title">{title}</div>
          <div class="warning-body">{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(title: str, subtitle: str | None = None) -> None:
    sub = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(
        f"""
        <div class="section-header">
          <h2>{title}</h2>
          {sub}
        </div>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str, status: object | None = None) -> None:
    status_html = status_pill(status) if status is not None else ""
    st.markdown(
        f"""
        <div class="page-hero">
          <div>
            <div class="eyebrow">NFL Prop War Room</div>
            <h1>{title}</h1>
            <p>{subtitle}</p>
          </div>
          <div>{status_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def player_card(player: str, team: str, position: str, projection: object, status: object = "") -> None:
    st.markdown(
        f"""
        <div class="player-card">
          <div class="player-name">{player}</div>
          <div class="player-meta">{team} / {position}</div>
          <div class="player-proj">{projection}</div>
          <div>{status_pill(status) if status else ""}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns={col: DISPLAY_NAMES.get(col, col.replace("_", " ").title()) for col in df.columns})


def safe_percent_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    result = df.copy()
    for col in result.columns:
        lower = col.lower()
        if "probability" in lower or "rate" in lower or "share" in lower:
            result[col] = pd.to_numeric(result[col], errors="coerce").map(
                lambda value: "" if pd.isna(value) else f"{value:.1%}"
            )
    return result


def safe_numeric_rounding(df: pd.DataFrame, digits: int = 4) -> pd.DataFrame:
    if df is None or df.empty:
        return df

    result = df.copy()

    for col in result.columns:
        series = result[col]

        if pd.api.types.is_numeric_dtype(series):
            result[col] = series.round(digits)
            continue

        converted = pd.to_numeric(series, errors="coerce")
        non_null_count = series.notna().sum()
        converted_count = converted.notna().sum()

        if non_null_count > 0 and converted_count / non_null_count >= 0.85:
            result[col] = converted.round(digits)
        else:
            result[col] = series

    return result


def presentation_table(df: pd.DataFrame | None) -> pd.DataFrame | None:
    if df is None or df.empty:
        return df
    rounded = safe_numeric_rounding(df)
    formatted = safe_percent_columns(rounded)
    return clean_column_names(formatted)


def render_status_cards(items: list[tuple[str, str]]) -> None:
    cols = st.columns(len(items))
    for col, (label, value) in zip(cols, items):
        with col:
            metric_card(label, value, value)


def sidebar_status() -> None:
    mode = value_from_status("projection_mode")
    readiness = value_from_status("final_live_readiness")
    leakage = value_from_status("leakage_status")
    live_output = value_from_status("live_betting_output_created")
    st.sidebar.markdown(
        f"""
        <div class="sidebar-brand">
          <div class="brand-title">NFL Prop War Room</div>
          <div class="brand-subtitle">Receptions V1</div>
          <div class="brand-chip">Historical Test Build</div>
        </div>
        <div class="sidebar-status">
          <div><span>Mode</span><strong>{mode}</strong></div>
          <div><span>Readiness</span><strong>{readiness}</strong></div>
          <div><span>Leakage</span><strong>{leakage}</strong></div>
          <div><span>Live betting</span><strong>{live_output}</strong></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def inject_global_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
          --bg: #07111f;
          --panel: #0f1b2d;
          --panel2: #101827;
          --border: #243247;
          --text: #e5edf7;
          --muted: #95a3b8;
          --red: #ff5d5d;
          --yellow: #ffd166;
          --green: #46e08c;
          --blue: #5ea0ff;
        }
        .stApp { background: radial-gradient(circle at top left, #13243a 0, #07111f 34%, #050914 100%); }
        .main .block-container { padding-top: 1.25rem; padding-bottom: 3rem; max-width: 1440px; }
        [data-testid="stSidebar"] { background: #060b14; border-right: 1px solid #1d2a3d; }
        [data-testid="stSidebar"] a { color: #cbd5e1; }
        [data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] p { color: #aab6c8; }
        .sidebar-brand {
          border: 1px solid #263247;
          background: linear-gradient(180deg, #132235, #0a1220);
          border-radius: 10px;
          padding: 1rem;
          margin-bottom: 1rem;
          box-shadow: 0 12px 32px rgba(0,0,0,.24);
        }
        .brand-title { color: #f8fafc; font-weight: 900; font-size: 1.05rem; }
        .brand-subtitle { color: #9fb3cc; font-weight: 700; margin-top: .15rem; }
        .brand-chip {
          margin-top: .7rem;
          display: inline-block;
          color: #ffd166;
          background: #30270d;
          border: 1px solid #6b5517;
          border-radius: 999px;
          padding: .22rem .55rem;
          font-size: .74rem;
          font-weight: 800;
        }
        .sidebar-status {
          border: 1px solid #1d2a3d;
          background: #0b1321;
          border-radius: 10px;
          padding: .8rem;
          margin-bottom: 1rem;
        }
        .sidebar-status div {
          display: flex;
          justify-content: space-between;
          gap: .75rem;
          padding: .35rem 0;
          border-bottom: 1px solid rgba(255,255,255,.06);
        }
        .sidebar-status div:last-child { border-bottom: 0; }
        .sidebar-status span { color: #8ea0b8; font-size: .78rem; }
        .sidebar-status strong { color: #edf2f7; font-size: .78rem; }
        .page-hero {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 1rem;
          padding: 1.25rem 1.35rem;
          border: 1px solid #29364a;
          border-radius: 12px;
          background: linear-gradient(135deg, rgba(17, 30, 48, .98), rgba(9, 15, 27, .98));
          box-shadow: 0 16px 40px rgba(0,0,0,.25);
          margin-bottom: 1rem;
        }
        .page-hero h1 { margin: .1rem 0 .35rem; color: #f8fafc; letter-spacing: 0; font-size: 2.1rem; }
        .page-hero p { margin: 0; color: #aab6c8; max-width: 820px; }
        .eyebrow { color: #5ea0ff; font-size: .78rem; font-weight: 900; text-transform: uppercase; letter-spacing: .08em; }
        .metric-card, .player-card, .info-card {
          background: linear-gradient(180deg, rgba(16, 28, 45, .98), rgba(9, 16, 29, .98));
          border: 1px solid #263247;
          border-radius: 10px;
          padding: .95rem;
          box-shadow: 0 10px 24px rgba(0,0,0,.2);
          min-height: 112px;
        }
        .metric-label { color: #8fa0b6; font-size: .78rem; text-transform: uppercase; font-weight: 800; margin-bottom: .45rem; }
        .metric-value { color: #f8fafc; font-size: 1.5rem; font-weight: 900; line-height: 1.1; margin-bottom: .35rem; }
        .metric-help { color: #8795aa; font-size: .8rem; margin-top: .35rem; }
        .status-pill {
          display: inline-block;
          padding: .22rem .6rem;
          border-radius: 999px;
          font-weight: 900;
          font-size: .76rem;
          border: 1px solid transparent;
          white-space: nowrap;
        }
        .status-pill.good { color: #8ff0b8; background: #0f3524; border-color: #246c47; }
        .status-pill.warn { color: #ffe199; background: #3d310d; border-color: #7a6017; }
        .status-pill.bad { color: #ffb4b4; background: #451717; border-color: #7a2a2a; }
        .status-pill.neutral { color: #cbd5e1; background: #1d293b; border-color: #334155; }
        .warning-banner {
          background: linear-gradient(135deg, #4a1515, #2a1116);
          border: 1px solid #923232;
          color: #ffe1e1;
          border-radius: 10px;
          padding: .95rem 1rem;
          margin: 1rem 0;
          box-shadow: 0 10px 26px rgba(0,0,0,.22);
        }
        .warning-title { color: #fff3f3; font-weight: 950; font-size: 1rem; margin-bottom: .25rem; }
        .warning-body { color: #ffc9c9; }
        .section-header { margin: 1.3rem 0 .65rem; }
        .section-header h2 { color: #f8fafc; font-size: 1.25rem; margin-bottom: .15rem; letter-spacing: 0; }
        .section-header p { color: #9aa9bd; margin: 0; }
        .player-name { color: #f8fafc; font-weight: 950; font-size: 1rem; }
        .player-meta { color: #9aa9bd; font-size: .82rem; margin: .25rem 0 .55rem; }
        .player-proj { color: #5ea0ff; font-size: 1.55rem; font-weight: 950; margin-bottom: .45rem; }
        div[data-testid="stDataFrame"] {
          border: 1px solid #263247;
          border-radius: 10px;
          overflow: hidden;
          box-shadow: 0 8px 20px rgba(0,0,0,.18);
        }
        .stTabs [data-baseweb="tab-list"] { gap: .35rem; }
        .stTabs [data-baseweb="tab"] {
          background: #111827;
          border-radius: 8px;
          border: 1px solid #263247;
          padding: .45rem .75rem;
        }
        hr { border-color: #263247; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def apply_global_styles() -> None:
    inject_global_styles()
