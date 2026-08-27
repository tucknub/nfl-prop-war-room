from __future__ import annotations

from src.fantasy.market_fantasy import build_market_fantasy_baseline


def _row(
    *,
    book,
    market,
    line,
    player="Jonathan Taylor",
    event_id="e1",
    market_key=None,
    over_price=-110,
    under_price=-110,
    commence_time="2026-09-13T17:00:00Z",
):
    return {
        "event_id": event_id,
        "commence_time": commence_time,
        "away_team": "IND",
        "home_team": "HOU",
        "book": book,
        "player": player,
        "market": market,
        "market_key": market_key or f"player_{market}",
        "line": line,
        "over_price": over_price,
        "under_price": under_price,
        "over_implied_prob": None,
        "under_implied_prob": None,
    }


def test_market_baseline_uses_consensus_lines_and_league_scoring():
    rows = [
        _row(book="DK", market="rushing_yards", line=72.5),
        _row(book="FD", market="rushing_yards", line=74.5),
        _row(book="B365", market="rushing_yards", line=73.5),
        _row(book="DK", market="receiving_yards", line=18.5),
        _row(book="FD", market="receiving_yards", line=20.5),
        _row(book="DK", market="receptions", line=2.5),
        _row(book="FD", market="receptions", line=2.5),
        _row(
            book="DK",
            market="anytime_td",
            line=0.5,
            over_price=-120,
            under_price=100,
        ),
        _row(
            book="FD",
            market="anytime_td",
            line=0.5,
            over_price=-110,
            under_price=-110,
        ),
    ]
    scoring = {
        "rush_yd": 0.1,
        "rec_yd": 0.1,
        "rec": 1.0,
        "rush_td": 6.0,
        "rec_td": 6.0,
    }

    result = build_market_fantasy_baseline(
        "Jonathan Taylor",
        "RB",
        scoring,
        rows,
    )

    assert result is not None
    by_market = {row.market: row for row in result.components}
    assert by_market["rushing_yards"].market_value == 73.5
    assert by_market["rushing_yards"].book_count == 3
    assert by_market["receiving_yards"].market_value == 19.5
    assert by_market["receptions"].market_value == 2.5
    assert 0.50 < by_market["anytime_td"].market_value < 0.56
    assert result.coverage_status == "FULL"
    assert result.fantasy_points > 14.0
    assert result.fallback_scoring_keys == ()


def test_market_baseline_ignores_alternate_ladders():
    rows = [
        _row(book="DK", market="rushing_yards", line=70.5),
        _row(book="FD", market="rushing_yards", line=72.5),
        _row(
            book="DK",
            market="rushing_yards",
            line=100.0,
            market_key="player_rush_yds_alternate",
        ),
        _row(
            book="FD",
            market="rushing_yards",
            line=110.0,
            market_key="player_rush_yds_alternate",
        ),
    ]

    result = build_market_fantasy_baseline(
        "Jonathan Taylor",
        "RB",
        {"rush_yd": 0.1},
        rows,
    )

    assert result is not None
    assert result.components[0].market_value == 71.5
    assert result.coverage_status == "THIN"


def test_market_baseline_does_not_mix_two_events():
    rows = [
        _row(
            book="DK",
            market="rushing_yards",
            line=10.5,
            event_id="preseason",
            commence_time="2026-08-27T23:00:00Z",
        ),
        _row(
            book="FD",
            market="rushing_yards",
            line=11.5,
            event_id="preseason",
            commence_time="2026-08-27T23:00:00Z",
        ),
        _row(
            book="DK",
            market="rushing_yards",
            line=75.5,
            event_id="week1",
            commence_time="2026-09-13T17:00:00Z",
        ),
        _row(
            book="DK",
            market="receiving_yards",
            line=20.5,
            event_id="week1",
            commence_time="2026-09-13T17:00:00Z",
        ),
        _row(
            book="DK",
            market="receptions",
            line=2.5,
            event_id="week1",
            commence_time="2026-09-13T17:00:00Z",
        ),
    ]

    result = build_market_fantasy_baseline(
        "Jonathan Taylor",
        "RB",
        {"rush_yd": 0.1, "rec_yd": 0.1, "rec": 1.0},
        rows,
    )

    assert result is not None
    # More supported market families wins; no preseason/week1 mixing.
    assert result.commence_time == "2026-09-13T17:00:00Z"
    assert {row.market for row in result.components} == {
        "rushing_yards",
        "receiving_yards",
        "receptions",
    }


def test_market_baseline_uses_actual_ppr_setting():
    rows = [
        _row(book="DK", market="receptions", line=6.5, player="Wide Receiver"),
        _row(book="FD", market="receptions", line=6.5, player="Wide Receiver"),
        _row(book="DK", market="receiving_yards", line=79.5, player="Wide Receiver"),
        _row(book="FD", market="receiving_yards", line=80.5, player="Wide Receiver"),
    ]

    standard = build_market_fantasy_baseline(
        "Wide Receiver",
        "WR",
        {"rec": 0.0, "rec_yd": 0.1},
        rows,
    )
    ppr = build_market_fantasy_baseline(
        "Wide Receiver",
        "WR",
        {"rec": 1.0, "rec_yd": 0.1},
        rows,
    )

    assert standard is not None
    assert ppr is not None
    assert round(ppr.fantasy_points - standard.fantasy_points, 2) == 6.5


def test_market_baseline_qb_combines_passing_and_rushing_context():
    rows = [
        _row(book="DK", market="passing_yards", line=249.5, player="Quarter Back"),
        _row(book="FD", market="passing_yards", line=250.5, player="Quarter Back"),
        _row(book="DK", market="passing_tds", line=1.5, player="Quarter Back"),
        _row(book="FD", market="passing_tds", line=1.5, player="Quarter Back"),
        _row(book="DK", market="interceptions", line=0.5, player="Quarter Back"),
        _row(book="FD", market="interceptions", line=0.5, player="Quarter Back"),
        _row(book="DK", market="rushing_yards", line=24.5, player="Quarter Back"),
        _row(book="FD", market="rushing_yards", line=25.5, player="Quarter Back"),
    ]

    result = build_market_fantasy_baseline(
        "Quarter Back",
        "QB",
        {
            "pass_yd": 0.04,
            "pass_td": 4.0,
            "pass_int": -2.0,
            "rush_yd": 0.1,
        },
        rows,
    )

    assert result is not None
    assert result.coverage_status == "FULL"
    # 250 pass yds (10) + 1.5 TD (6) - 0.5 INT (1) + 25 rush (2.5)
    assert round(result.fantasy_points, 2) == 17.5


def test_market_baseline_reports_scoring_fallbacks():
    rows = [
        _row(book="DK", market="rushing_yards", line=50.5),
    ]

    result = build_market_fantasy_baseline(
        "Jonathan Taylor",
        "RB",
        {},
        rows,
    )

    assert result is not None
    assert result.fallback_scoring_keys == ("rush_yd",)


def test_market_baseline_returns_none_without_matching_markets():
    result = build_market_fantasy_baseline(
        "Jonathan Taylor",
        "RB",
        {"rush_yd": 0.1},
        [
            _row(
                book="DK",
                market="passing_yards",
                line=250.5,
                player="Different Player",
            )
        ],
    )

    assert result is None


def test_fantasy_hq_exposes_market_implied_baseline():
    from pathlib import Path

    page = (
        Path(__file__).resolve().parents[1]
        / "dashboard"
        / "pages"
        / "11_Fantasy_HQ.py"
    ).read_text(encoding="utf-8")

    assert "Market-Implied Fantasy Baseline" in page
    assert "build_market_fantasy_baseline" in page
    assert "Consensus base prop lines" in page
    assert "PARLAY_API_KEY" in page
