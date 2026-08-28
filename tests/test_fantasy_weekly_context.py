from __future__ import annotations

import threading
import time

import pytest

from src.fantasy import weekly_context


class FakeSleeperClient:
    thread_ids: set[int] = set()
    lock = threading.Lock()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def fetch_matchups(self, league_id: str, week: int):
        with self.lock:
            self.thread_ids.add(threading.get_ident())
        time.sleep(0.02)
        if league_id == "league-bad":
            raise RuntimeError("matchups unavailable")
        return (f"matchup:{league_id}:{week}",)

    def fetch_transactions(self, league_id: str, week: int):
        with self.lock:
            self.thread_ids.add(threading.get_ident())
        time.sleep(0.01)
        if league_id == "league-two" and week == 2:
            raise RuntimeError("transactions unavailable")
        return (f"tx:{league_id}:{week}",)


def test_weekly_context_fetch_is_bounded_parallel_and_ordered(monkeypatch) -> None:
    FakeSleeperClient.thread_ids = set()
    monkeypatch.setattr(weekly_context, "SleeperClient", FakeSleeperClient)

    rows = weekly_context.fetch_league_weekly_contexts(
        ("league-one", "league-two", "league-three"),
        current_week=3,
        transaction_weeks=(1, 2, 3),
        max_workers=3,
    )

    assert [row.league_id for row in rows] == [
        "league-one",
        "league-two",
        "league-three",
    ]
    assert len(FakeSleeperClient.thread_ids) >= 2
    assert rows[0].matchups == ("matchup:league-one:3",)
    assert rows[0].transactions == (
        "tx:league-one:1",
        "tx:league-one:2",
        "tx:league-one:3",
    )
    assert rows[0].errors == ()


def test_weekly_context_errors_are_isolated_per_league(monkeypatch) -> None:
    FakeSleeperClient.thread_ids = set()
    monkeypatch.setattr(weekly_context, "SleeperClient", FakeSleeperClient)

    rows = weekly_context.fetch_league_weekly_contexts(
        ("league-bad", "league-two"),
        current_week=3,
        transaction_weeks=(2, 3),
        max_workers=2,
    )

    bad, two = rows
    assert bad.matchups == ()
    assert bad.transactions == (
        "tx:league-bad:2",
        "tx:league-bad:3",
    )
    assert bad.errors == ("matchup: matchups unavailable",)

    assert two.matchups == ("matchup:league-two:3",)
    assert two.transactions == ("tx:league-two:3",)
    assert two.errors == (
        "Week 2 transactions: transactions unavailable",
    )


def test_weekly_context_validates_worker_bound(monkeypatch) -> None:
    monkeypatch.setattr(weekly_context, "SleeperClient", FakeSleeperClient)

    with pytest.raises(ValueError, match="between 1 and 8"):
        weekly_context.fetch_league_weekly_contexts(
            ("league-one",),
            current_week=1,
            transaction_weeks=(1,),
            max_workers=0,
        )
