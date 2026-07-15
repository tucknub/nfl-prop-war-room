from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

import streamlit as st
import streamlit.components.v1 as components


@dataclass(frozen=True)
class ControlStateDecision:
    value: object | None
    invalid_query: bool
    source: str
    query_changed: bool


def resolve_control_state(
    options: Iterable[object],
    requested: object | None,
    session_value: object | None,
    *,
    default: object | None = None,
    query_present: bool = False,
    query_changed: bool = False,
) -> ControlStateDecision:
    """Resolve one control without allowing a stale URL value to beat a widget change."""
    available = list(options)
    fallback = session_value if session_value in available else (
        default if default in available else (available[0] if available else None)
    )
    if query_present and requested not in available:
        return ControlStateDecision(fallback, True, "invalid_query", query_changed)
    if query_present and query_changed:
        return ControlStateDecision(requested, False, "query", True)
    if session_value in available:
        return ControlStateDecision(session_value, False, "widget", query_changed)
    if query_present:
        return ControlStateDecision(requested, False, "query", query_changed)
    return ControlStateDecision(fallback, False, "default", query_changed)


def query_value(name: str) -> str:
    value = st.query_params.get(name, "")
    return value[0] if isinstance(value, list) and value else str(value)


def initialize_query_control(
    page: str,
    query_key: str,
    widget_key: str,
    options: Iterable[object],
    *,
    default: object | None = None,
    parser: Callable[[str], object | None] | None = None,
) -> ControlStateDecision:
    """Apply a URL value only on initial load or when that browser URL value changes."""
    available = list(options)
    raw = query_value(query_key)
    present = raw != ""
    requested = parser(raw) if present and parser else (raw if present else None)
    marker_key = f"_pw_query_seen::{page}::{query_key}"
    previous = st.session_state.get(marker_key, object())
    changed = previous != raw
    decision = resolve_control_state(
        available,
        requested,
        st.session_state.get(widget_key),
        default=default,
        query_present=present,
        query_changed=changed,
    )
    st.session_state[marker_key] = raw
    if decision.value is not None and st.session_state.get(widget_key) != decision.value:
        st.session_state[widget_key] = decision.value
    return decision


def update_query_from_widget(
    query_key: str,
    widget_key: str,
    *,
    clear_query: tuple[str, ...] = (),
) -> None:
    """Make the newly selected widget value authoritative and deep-linkable."""
    value = st.session_state.get(widget_key)
    if value in {None, ""}:
        st.query_params.pop(query_key, None)
    else:
        st.query_params[query_key] = str(value)
    for key in clear_query:
        if key != query_key:
            st.query_params.pop(key, None)


def parse_int(value: str) -> int | None:
    return int(value) if value.isdigit() else None


def enable_browser_history_sync() -> None:
    """Reload a deep-link page when browser Back/Forward activates another URL."""
    components.html(
        """
        <script>
        (() => {
          let host;
          try { host = window.top; void host.location.href; }
          catch (_) { host = window.parent; }
          if (host.__propwarHistorySyncInstalled) return;
          host.__propwarHistorySyncInstalled = true;
          host.addEventListener("popstate", () => host.setTimeout(() => host.location.reload(), 0));
        })();
        </script>
        """,
        height=0,
    )
