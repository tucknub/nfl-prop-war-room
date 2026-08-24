from __future__ import annotations

from dashboard import access_control, public_copy
from src.margin import state_store


AUTH = {
    "redirect_uri": "https://propwar.streamlit.app/oauth2callback",
    "cookie_secret": "cookie-secret",
    "client_id": "client-id",
    "client_secret": "client-secret",
    "server_metadata_url": "https://accounts.google.com/.well-known/openid-configuration",
}


def auth_secrets(**extra) -> dict:
    return {
        "auth": dict(AUTH),
        "PROPWAR_OWNER_EMAIL": "owner@example.com",
        "MARGIN_GITHUB_TOKEN": "token",
        "MARGIN_GITHUB_REPO": "tucknub/propwar-private-state",
        **extra,
    }


def test_partial_auth_fails_closed_and_hides_personal_tools() -> None:
    assert access_control.access_mode({}, {}) == "AUTH_UNAVAILABLE"
    assert access_control.access_mode({"PROPWAR_OWNER_EMAIL": "owner@example.com"}, {}) == "AUTH_UNAVAILABLE"
    assert access_control.access_mode({"MARGIN_ADMIN_KEY": "legacy-secret"}, {}) == "AUTH_UNAVAILABLE"


def test_configured_auth_hides_personal_tools_until_owner_logs_in() -> None:
    secrets = auth_secrets()
    assert access_control.access_mode(secrets, {}) == "ANONYMOUS"
    assert access_control.access_mode(
        secrets,
        {"is_logged_in": True, "email": "other@example.com", "email_verified": True},
    ) == "NON_OWNER"


def test_owner_email_is_case_insensitive_and_requires_verified_email_when_claim_present() -> None:
    secrets = auth_secrets()
    owner = {"is_logged_in": True, "email": "OWNER@example.com", "email_verified": True}
    assert access_control.owner_authenticated(secrets, owner) is True
    assert access_control.access_mode(secrets, owner) == "OWNER"
    unverified = {"is_logged_in": True, "email": "owner@example.com", "email_verified": False}
    assert access_control.owner_authenticated(secrets, unverified) is False
    assert access_control.access_mode(secrets, unverified) == "NON_OWNER"


def test_oidc_write_config_requires_owner_identity(monkeypatch) -> None:
    secrets = auth_secrets()
    config = state_store.config_from_secrets(secrets)
    assert config is not None
    assert config["auth_mode"] == "OIDC_OWNER"

    monkeypatch.setattr(
        state_store,
        "_current_streamlit_user",
        lambda: {"is_logged_in": True, "email": "owner@example.com", "email_verified": True},
    )
    assert state_store.owner_write_authorized(config) is True

    monkeypatch.setattr(
        state_store,
        "_current_streamlit_user",
        lambda: {"is_logged_in": True, "email": "other@example.com", "email_verified": True},
    )
    assert state_store.owner_write_authorized(config) is False


def test_legacy_admin_key_no_longer_authorizes_or_configures_writes() -> None:
    config = state_store.config_from_secrets({
        "MARGIN_GITHUB_TOKEN": "token",
        "MARGIN_ADMIN_KEY": "secret",
    })
    assert config is None
    assert state_store.owner_write_authorized({"auth_mode": "LEGACY_ADMIN", "admin_key": "secret"}) is False


def test_public_copy_uses_historical_wording_until_current_partition_is_published(monkeypatch) -> None:
    monkeypatch.setattr(
        public_copy,
        "load_operational_status",
        lambda: {"status": "HISTORICAL_ONLY", "season": 2025, "published_through_week": 18},
    )
    historical = public_copy.role_home_copy()
    assert historical["hero_title"] == "Latest NFL role research"
    assert historical["page_title"] == "Latest NFL Role Research"

    monkeypatch.setattr(
        public_copy,
        "load_operational_status",
        lambda: {"status": "PUBLISHED", "season": 2026, "published_through_week": 1},
    )
    current = public_copy.role_home_copy()
    assert current["hero_title"] == "What changed in NFL roles?"
    assert current["page_title"] == "This Week in NFL Roles"
