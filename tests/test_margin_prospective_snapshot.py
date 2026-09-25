from __future__ import annotations

import pandas as pd
import pytest

from scripts import snapshot_margin_prospective as snapshot


def test_frozen_model_sources_have_not_drifted() -> None:
    freeze = snapshot.load_freeze()
    snapshot.assert_frozen_sources(freeze)


def test_prospective_ledger_refuses_pre_week4_state() -> None:
    freeze = snapshot.load_freeze()
    state = {
        "season": 2026,
        "current_week": 3,
        "completed_week": 2,
        "used_teams": ["JAX", "TB"],
        "cumulative_score": 20.0,
        "pool": {"size": 42},
    }
    with pytest.raises(RuntimeError, match="starts Week 4"):
        snapshot.build_expected_points_audit(state, pd.DataFrame(), freeze)
