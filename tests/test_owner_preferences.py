from __future__ import annotations

from src.owner.preferences import (
    DEFAULT_OWNER_PREFS_PATH,
    private_owner_preferences_config,
    sleeper_username_from_preferences,
)


def test_owner_preferences_reuse_private_propwar_state_repo():
    config = private_owner_preferences_config(
        {
            "MARGIN_GITHUB_TOKEN": "token",
            "MARGIN_GITHUB_REPO": "owner/private-state",
            "MARGIN_GITHUB_BRANCH": "main",
        }
    )

    assert config is not None
    assert config["repo"] == "owner/private-state"
    assert config["branch"] == "main"
    assert config["path"] == DEFAULT_OWNER_PREFS_PATH


def test_owner_preferences_allow_custom_path():
    config = private_owner_preferences_config(
        {
            "MARGIN_GITHUB_TOKEN": "token",
            "MARGIN_GITHUB_REPO": "owner/private-state",
            "PROPWAR_OWNER_PREFS_PATH": "prefs/owner.json",
        }
    )

    assert config is not None
    assert config["path"] == "prefs/owner.json"


def test_sleeper_username_is_trimmed_from_private_preferences():
    assert (
        sleeper_username_from_preferences({"sleeper_username": "  Tucknub  "})
        == "Tucknub"
    )
    assert sleeper_username_from_preferences({}) == ""
