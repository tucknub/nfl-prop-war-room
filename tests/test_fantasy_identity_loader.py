from __future__ import annotations

import sys
from types import SimpleNamespace

import pandas as pd

from src.fantasy.identity import MATCHED, load_ffverse_player_ids, resolve_sleeper_player


class _FakePolarsFrame:
    def __init__(self, frame: pd.DataFrame) -> None:
        self._frame = frame

    def to_pandas(self) -> pd.DataFrame:
        return self._frame.copy()


def test_load_ffverse_player_ids_uses_installed_nflreadpy_loader(monkeypatch):
    expected = pd.DataFrame(
        {
            "sleeper_id": ["4984"],
            "gsis_id": ["00-0034796"],
            "yahoo_id": ["30123"],
        }
    )
    fake_module = SimpleNamespace(load_ff_playerids=lambda: _FakePolarsFrame(expected))
    monkeypatch.setitem(sys.modules, "nflreadpy", fake_module)

    loaded = load_ffverse_player_ids()

    assert loaded.to_dict("records") == expected.to_dict("records")


def test_integral_numeric_provider_ids_do_not_create_false_identity_conflicts():
    frame = pd.DataFrame(
        {
            "sleeper_id": [4984.0],
            "gsis_id": ["00-0034796"],
            "yahoo_id": [30123.0],
            "name": ["Josh Allen"],
            "position": ["QB"],
            "team": ["BUF"],
        }
    )

    result = resolve_sleeper_player(
        4984,
        ffverse_player_ids=frame,
        propwar_player_ids={"00-0034796"},
        sleeper_metadata={
            "full_name": "Josh Allen",
            "position": "QB",
            "team": "BUF",
            "yahoo_id": 30123,
        },
    )

    assert result.status == MATCHED
    assert result.sleeper_id == "4984"
    assert result.yahoo_id == "30123"


def test_current_sleeper_team_is_preferred_when_ffverse_team_lags():
    frame = pd.DataFrame(
        {
            "sleeper_id": ["123"],
            "gsis_id": ["00-0000123"],
            "name": ["Player One"],
            "position": ["WR"],
            "team": ["TEN"],
        }
    )

    result = resolve_sleeper_player(
        "123",
        ffverse_player_ids=frame,
        propwar_player_ids={"00-0000123"},
        sleeper_metadata={"full_name": "Player One", "position": "WR", "team": "IND"},
    )

    assert result.status == MATCHED
    assert result.team == "IND"
    assert "TEAM_METADATA_DIFFERS" in result.reason_codes
