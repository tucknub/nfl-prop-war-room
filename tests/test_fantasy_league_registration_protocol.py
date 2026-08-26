from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.fantasy.league_registration_protocol import (
    LEAGUE_SEASON_UPSERT,
    build_league_season_upsert_command,
)
from src.fantasy.persistence import LeagueSeasonIdentity
from src.fantasy.persistence_protocol import (
    FANTASY_PERSISTENCE_PROTOCOL_VERSION,
    JAVASCRIPT_MAX_SAFE_INTEGER,
    UnsafePersistenceCommand,
)


FIXTURE_PATH = Path("tests/fixtures/fantasy_league_registration_command_v1.json")


def _identity() -> LeagueSeasonIdentity:
    return LeagueSeasonIdentity(
        league_season_id="ffl:2026",
        platform="SLEEPER",
        platform_league_id="league-2026",
        season="2026",
    )


def _command():
    return build_league_season_upsert_command(
        _identity(),
        league_family_id=" ffl ",
        family_display_name=" Franchise Football League ",
        season_display_name=" Franchise Football League 2026 ",
        created_at_ms=1787760000000,
        family_metadata={"source": "owner_config"},
        season_metadata={"platform_status": "in_season"},
    )


def test_python_registration_export_matches_cross_language_fixture_exactly():
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    command = _command()

    assert command == fixture
    assert command["protocol_version"] == FANTASY_PERSISTENCE_PROTOCOL_VERSION
    assert command["kind"] == LEAGUE_SEASON_UPSERT
    assert "sql" not in command
    assert command["league_family_id"] == "ffl"
    assert json.loads(command["family_metadata_json"]) == {"source": "owner_config"}
    assert json.loads(command["season_metadata_json"]) == {
        "platform_status": "in_season"
    }


def test_registration_export_is_strict_json_and_deterministic():
    first = _command()
    second = _command()

    assert first == second
    encoded = json.dumps(first, allow_nan=False, separators=(",", ":"))
    assert json.loads(encoded) == first


def test_registration_export_defaults_metadata_to_empty_objects():
    command = build_league_season_upsert_command(
        _identity(),
        league_family_id="ffl",
        family_display_name="Franchise Football League",
        season_display_name="Franchise Football League 2026",
        created_at_ms=0,
    )

    assert command["family_metadata_json"] == "{}"
    assert command["season_metadata_json"] == "{}"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"league_family_id": " "}, "league_family_id is required"),
        ({"family_display_name": ""}, "family_display_name is required"),
        ({"season_display_name": 3}, "season_display_name must be a string"),
        (
            {"created_at_ms": JAVASCRIPT_MAX_SAFE_INTEGER + 1},
            "created_at_ms must be a non-negative JavaScript safe integer",
        ),
        (
            {"family_metadata": ["not", "mapping"]},
            "family_metadata must be a mapping",
        ),
        (
            {"season_metadata": {"bad": float("nan")}},
            "season_metadata is not valid JSON",
        ),
    ],
)
def test_registration_export_rejects_unsafe_transport_values(kwargs, message):
    values = {
        "league_family_id": "ffl",
        "family_display_name": "Franchise Football League",
        "season_display_name": "Franchise Football League 2026",
        "created_at_ms": 1,
        "family_metadata": None,
        "season_metadata": None,
    }
    values.update(kwargs)

    with pytest.raises(UnsafePersistenceCommand, match=message):
        build_league_season_upsert_command(_identity(), **values)
