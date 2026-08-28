from __future__ import annotations

import streamlit as st

from src.owner.preferences import (
    fetch_owner_preferences,
    sleeper_username_from_preferences,
)


SLEEPER_USERNAME_SESSION_KEY = "fantasy_hq_sleeper_username"
SLEEPER_USERNAME_QUERY_KEY = "fh_sleeper"


def _mapping(value) -> dict:
    try:
        return dict(value.to_dict()) if hasattr(value, "to_dict") else dict(value)
    except Exception:
        return {}


def _secret_default(key: str) -> str:
    try:
        return str(st.secrets.get(key, "") or "").strip()
    except Exception:
        return ""


@st.cache_data(ttl=300, show_spinner=False)
def _private_owner_preferences(
    repo: str,
    branch: str,
    path: str,
    token: str,
) -> dict:
    secrets = {
        "MARGIN_GITHUB_REPO": repo,
        "MARGIN_GITHUB_BRANCH": branch,
        "MARGIN_GITHUB_TOKEN": token,
        "PROPWAR_OWNER_PREFS_PATH": path,
    }
    try:
        return fetch_owner_preferences(secrets)
    except Exception:
        return {}


def private_sleeper_username() -> str:
    repo = _secret_default("MARGIN_GITHUB_REPO")
    token = _secret_default("MARGIN_GITHUB_TOKEN")
    if not repo or not token:
        return ""
    branch = _secret_default("MARGIN_GITHUB_BRANCH") or "main"
    path = _secret_default("PROPWAR_OWNER_PREFS_PATH") or "owner/preferences.json"
    preferences = _private_owner_preferences(repo, branch, path, token)
    return sleeper_username_from_preferences(preferences)


def remembered_sleeper_username() -> str:
    query_value = str(st.query_params.get(SLEEPER_USERNAME_QUERY_KEY) or "").strip()
    if query_value:
        st.session_state[SLEEPER_USERNAME_SESSION_KEY] = query_value
        return query_value

    session_value = str(
        st.session_state.get(SLEEPER_USERNAME_SESSION_KEY) or ""
    ).strip()
    if session_value:
        return session_value

    secret_value = _secret_default("FANTASY_HQ_SLEEPER_USERNAME")
    if secret_value:
        return secret_value

    private_value = private_sleeper_username()
    if private_value:
        st.session_state[SLEEPER_USERNAME_SESSION_KEY] = private_value
    return private_value


def store_sleeper_username(username: str) -> None:
    normalized = str(username or "").strip()
    if not normalized:
        return
    st.session_state[SLEEPER_USERNAME_SESSION_KEY] = normalized
    if str(st.query_params.get(SLEEPER_USERNAME_QUERY_KEY) or "").strip() != normalized:
        st.query_params[SLEEPER_USERNAME_QUERY_KEY] = normalized


__all__ = [
    "SLEEPER_USERNAME_QUERY_KEY",
    "SLEEPER_USERNAME_SESSION_KEY",
    "private_sleeper_username",
    "remembered_sleeper_username",
    "store_sleeper_username",
]
