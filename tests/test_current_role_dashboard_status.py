from __future__ import annotations

import json
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard"
if str(DASHBOARD) not in sys.path:
    sys.path.insert(0, str(DASHBOARD))

import research_data  # noqa: E402


def _clear() -> None:
    research_data.load_operational_status.cache_clear()
    research_data.load_role_data.cache_clear()
    research_data.load_situational_data.cache_clear()
    research_data.load_production_data.cache_clear()
    research_data.load_opportunity_events.cache_clear()


def test_dashboard_discovers_live_season_partition_and_status(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "outputs" / "role_research"
    output.mkdir(parents=True)
    canonical = pd.DataFrame(
        [
            {
                "season": 2026,
                "week": 1,
                "game_id": "2026_01_AAA_BBB",
                "player_id": "P1",
                "player_name": "Player One",
                "team": "AAA",
                "position": "RB",
                "role_family": "rb_carry_share",
                "metric_all": 0.6,
                "metric_normal": 0.6,
                "raw_opportunities_all": 12,
                "raw_opportunities_normal": 12,
                "team_opportunities_all": 20,
                "team_opportunities_normal": 20,
                "qualifying_game": True,
                "data_quality_pass": True,
                "active_status": "ACT",
                "snap_share": 0.7,
                "identity_resolved": True,
                "game_partition_complete": True,
                "participation_play_coverage": pd.NA,
                "source_version": "test",
                "confirmed_partial_game": False,
                "suspected_partial_game": False,
                "suspected_partial_corroborated": False,
                "partial_game_status": "unreviewed",
                "partial_game_reason": "CURRENT_SEASON_MANUAL_PARTIAL_REVIEW_NOT_PROVIDED",
            }
        ]
    )
    canonical.to_csv(
        output / "canonical_role_2026_live.csv.gz",
        index=False,
        compression={"method": "gzip", "compresslevel": 9, "mtime": 0},
    )
    (output / "role_research_status_2026.json").write_text(
        json.dumps(
            {
                "season": 2026,
                "status": "PUBLISHED",
                "published_through_week": 1,
                "message": "Published through Week 1.",
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(research_data, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(research_data, "HISTORICAL_CANONICAL_FILES", ())
    _clear()
    try:
        assert research_data.available_seasons() == [2026]
        assert research_data.available_weeks(2026) == [1]
        assert research_data.operational_status_text() == "2026 current-season data published through Week 1."
    finally:
        _clear()
