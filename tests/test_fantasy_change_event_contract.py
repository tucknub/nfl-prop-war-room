from __future__ import annotations

import pytest

from src.fantasy.changes import FantasyChangeEvent


def test_change_event_requires_both_snapshot_ids():
    with pytest.raises(ValueError, match="before_snapshot_id and after_snapshot_id"):
        FantasyChangeEvent(
            event_type="STARTER_CHANGED",
            platform="SLEEPER",
            platform_league_id="league-1",
            season="2026",
            before_snapshot_id="",
            after_snapshot_id="snap-2",
        )

    with pytest.raises(ValueError, match="before_snapshot_id and after_snapshot_id"):
        FantasyChangeEvent(
            event_type="STARTER_CHANGED",
            platform="SLEEPER",
            platform_league_id="league-1",
            season="2026",
            before_snapshot_id="snap-1",
            after_snapshot_id="",
        )
