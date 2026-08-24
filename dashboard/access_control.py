from __future__ import annotations

from typing import Any, Mapping


OWNER_EMAIL_SECRET = "PROPWAR_OWNER_EMAIL"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def owner_auth_configured(secrets: Mapping[str, Any]) -> bool:
    """Return True only when OIDC settings and an explicit owner email exist.

    This intentionally treats partial configuration as disabled so deployment can
    migrate safely from the legacy Margin admin-key flow without locking the owner
    out of the app.
    """
    auth = _mapping(secrets.get("auth"))
    owner_email = str(secrets.get(OWNER_EMAIL_SECRET, "")).strip()
    required = ["redirect_uri", "cookie_secret", "client_id", "client_secret", "server_metadata_url"]
    return bool(owner_email and all(str(auth.get(key, "")).strip() for key in required))


def owner_email(secrets: Mapping[str, Any]) -> str:
    return str(secrets.get(OWNER_EMAIL_SECRET, "")).strip().casefold()


def user_email(user: Mapping[str, Any] | None) -> str:
    return str(_mapping(user).get("email", "")).strip().casefold()


def user_is_logged_in(user: Mapping[str, Any] | None) -> bool:
    return bool(_mapping(user).get("is_logged_in", False))


def owner_authenticated(secrets: Mapping[str, Any], user: Mapping[str, Any] | None) -> bool:
    if not owner_auth_configured(secrets) or not user_is_logged_in(user):
        return False
    expected = owner_email(secrets)
    actual = user_email(user)
    if not expected or not actual or actual != expected:
        return False
    verified = _mapping(user).get("email_verified")
    return verified is not False


def access_mode(secrets: Mapping[str, Any], user: Mapping[str, Any] | None) -> str:
    """Describe which Margin access path should be active.

    LEGACY_ADMIN: OIDC is not fully configured, so the existing admin-key flow
    remains available during migration.
    OWNER: the configured owner is authenticated through OIDC.
    ANONYMOUS: OIDC is configured but nobody is logged in.
    NON_OWNER: OIDC is configured and a different account is logged in.
    """
    if not owner_auth_configured(secrets):
        return "LEGACY_ADMIN"
    if owner_authenticated(secrets, user):
        return "OWNER"
    if user_is_logged_in(user):
        return "NON_OWNER"
    return "ANONYMOUS"
