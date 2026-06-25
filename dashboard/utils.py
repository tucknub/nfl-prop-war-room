from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import streamlit as st


READY_STATUSES = {"GO", "READY", "PASS", "HIGH"}
WARN_STATUSES = {"NEEDS DATA", "REVIEW", "CHECK", "WARNING", "MEDIUM", "HISTORICAL TEST ONLY"}
BAD_STATUSES = {"NO-GO", "BLOCKED", "NOT READY", "FAIL", "LOW", "DO NOT USE", "TEAM_VERIFY"}


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


def status_badge(status: object) -> str:
    text = "UNKNOWN" if pd.isna(status) else str(status)
    level = status_level(text)
    colors = {
        "good": ("#113b26", "#3ddc84"),
        "warn": ("#433509", "#ffd166"),
        "bad": ("#4a1515", "#ff6b6b"),
        "neutral": ("#263241", "#b7c0cc"),
    }
    bg, fg = colors[level]
    return (
        f"<span style='display:inline-block;padding:0.2rem 0.55rem;border-radius:999px;"
        f"background:{bg};color:{fg};font-weight:700;font-size:0.82rem'>{text}</span>"
    )


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


def render_status_cards(items: list[tuple[str, str]]) -> None:
    cols = st.columns(len(items))
    for col, (label, value) in zip(cols, items):
        with col:
            st.markdown(
                f"""
                <div class="status-card">
                  <div class="status-label">{label}</div>
                  <div>{status_badge(value)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def apply_global_styles() -> None:
    st.markdown(
        """
        <style>
        .main .block-container { padding-top: 1.5rem; max-width: 1400px; }
        .war-header {
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 1rem 1.2rem;
            margin-bottom: 1rem;
        }
        .war-header h1 { color: #f0f6fc; margin: 0; letter-spacing: 0; }
        .war-header p { color: #b7c0cc; margin: 0.35rem 0 0; }
        .status-card {
            background: #111827;
            border: 1px solid #263241;
            border-radius: 8px;
            padding: 0.8rem;
            min-height: 88px;
        }
        .status-label {
            color: #9ca3af;
            font-size: 0.82rem;
            text-transform: uppercase;
            margin-bottom: 0.45rem;
        }
        .warning-band {
            background: #4a1515;
            color: #ffd6d6;
            border: 1px solid #ff6b6b;
            border-radius: 8px;
            padding: 0.85rem 1rem;
            font-weight: 800;
            margin: 1rem 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
