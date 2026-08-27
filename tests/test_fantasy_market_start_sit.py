from __future__ import annotations

from src.fantasy.lineup_check import LineupCheck, LineupPlayerFact, LineupSlotCheck
from src.fantasy.market_start_sit import (
    CLOSE,
    FILL,
    INCOMPLETE,
    KEEP,
    SWAP,
    build_market_start_sit_board,
)


def _player(pid, name, pos):
    return LineupPlayerFact(
        player_id=pid,
        name=name,
        position=pos,
        fantasy_positions=(pos,),
        nfl_team="IND",
        status="Active",
    )


def _row(player, market, line, *, book="DK", event_id="e1"):
    return {
        "event_id": event_id,
        "commence_time": "2026-09-13T17:00:00Z",
        "away_team": "IND",
        "home_team": "HOU",
        "book": book,
        "player": player,
        "market": market,
        "market_key": f"player_{market}",
        "line": line,
        "over_price": -110,
        "under_price": -110,
        "over_implied_prob": None,
        "under_implied_prob": None,
    }


def _covered_rows(player, *, rec=4.5, rec_yd=55.5, td=True):
    rows = [
        _row(player, "receptions", rec, book="DK"),
        _row(player, "receptions", rec, book="FD"),
        _row(player, "receiving_yards", rec_yd, book="DK"),
        _row(player, "receiving_yards", rec_yd, book="FD"),
    ]
    if td:
        rows.extend(
            [
                _row(player, "anytime_td", 0.5, book="DK"),
                _row(player, "anytime_td", 0.5, book="FD"),
            ]
        )
    return rows


def _lineup(starter, bench):
    return LineupCheck(
        slots=(
            LineupSlotCheck(
                slot_index=0,
                slot="WR",
                starter=starter,
                eligible_alternatives=tuple(bench),
                state="READY",
                reason="No factual lineup-status issue.",
            ),
        ),
        bench=tuple(bench),
        used_matchup_lineup=False,
    )


def test_market_start_sit_recommends_clear_bench_upgrade():
    starter = _player("s", "Starter Wideout", "WR")
    bench = _player("b", "Bench Wideout", "WR")
    rows = [
        *_covered_rows("Starter Wideout", rec=3.5, rec_yd=45.5),
        *_covered_rows("Bench Wideout", rec=6.5, rec_yd=82.5),
    ]

    board = build_market_start_sit_board(
        _lineup(starter, (bench,)),
        {"rec": 1.0, "rec_yd": 0.1, "rec_td": 6.0},
        {
            "s": {"position": "WR"},
            "b": {"position": "WR"},
        },
        rows,
    )

    row = board.slots[0]
    assert row.verdict == SWAP
    assert row.best_bench is not None
    assert row.best_bench.name == "Bench Wideout"
    assert row.edge_points is not None and row.edge_points >= 1.0
    assert board.swap_count == 1


def test_market_start_sit_keeps_clear_market_favorite():
    starter = _player("s", "Starter Wideout", "WR")
    bench = _player("b", "Bench Wideout", "WR")
    rows = [
        *_covered_rows("Starter Wideout", rec=7.5, rec_yd=90.5),
        *_covered_rows("Bench Wideout", rec=3.5, rec_yd=40.5),
    ]

    board = build_market_start_sit_board(
        _lineup(starter, (bench,)),
        {"rec": 1.0, "rec_yd": 0.1, "rec_td": 6.0},
        {"s": {"position": "WR"}, "b": {"position": "WR"}},
        rows,
    )

    assert board.slots[0].verdict == KEEP


def test_market_start_sit_marks_close_call_inside_one_point():
    starter = _player("s", "Starter Wideout", "WR")
    bench = _player("b", "Bench Wideout", "WR")
    rows = [
        *_covered_rows("Starter Wideout", rec=5.0, rec_yd=60.0),
        *_covered_rows("Bench Wideout", rec=5.0, rec_yd=66.0),
    ]

    board = build_market_start_sit_board(
        _lineup(starter, (bench,)),
        {"rec": 1.0, "rec_yd": 0.1, "rec_td": 6.0},
        {"s": {"position": "WR"}, "b": {"position": "WR"}},
        rows,
    )

    assert board.slots[0].verdict == CLOSE


def test_market_start_sit_does_not_fake_swap_without_starter_coverage():
    starter = _player("s", "Uncovered Starter", "WR")
    bench = _player("b", "Bench Wideout", "WR")
    rows = _covered_rows("Bench Wideout", rec=7.0, rec_yd=90.0)

    board = build_market_start_sit_board(
        _lineup(starter, (bench,)),
        {"rec": 1.0, "rec_yd": 0.1, "rec_td": 6.0},
        {"s": {"position": "WR"}, "b": {"position": "WR"}},
        rows,
    )

    assert board.slots[0].verdict == INCOMPLETE
    assert board.slots[0].edge_points is None


def test_market_start_sit_can_fill_open_slot_from_covered_bench():
    bench = _player("b", "Bench Wideout", "WR")
    lineup = LineupCheck(
        slots=(
            LineupSlotCheck(
                slot_index=0,
                slot="WR",
                starter=None,
                eligible_alternatives=(bench,),
                state="NEEDS_ACTION",
                reason="Starter slot is open.",
            ),
        ),
        bench=(bench,),
        used_matchup_lineup=False,
    )

    board = build_market_start_sit_board(
        lineup,
        {"rec": 1.0, "rec_yd": 0.1, "rec_td": 6.0},
        {"b": {"position": "WR"}},
        _covered_rows("Bench Wideout"),
    )

    assert board.slots[0].verdict == FILL
    assert board.fill_count == 1


def test_fantasy_hq_exposes_market_assisted_start_sit():
    from pathlib import Path

    page = (
        Path(__file__).resolve().parents[1]
        / "dashboard"
        / "pages"
        / "11_Fantasy_HQ.py"
    ).read_text(encoding="utf-8")

    assert "Market-Assisted Start/Sit" in page
    assert "build_market_start_sit_board" in page
    assert "Market edge" in page
    assert "FULL/PARTIAL" in page
