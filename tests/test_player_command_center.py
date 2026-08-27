from __future__ import annotations

from dashboard.player_command_center import (
    CHECK,
    NO_EDGE,
    SHOP,
    build_best_price_rows,
    build_player_prop_action,
    build_player_prop_context,
    player_prop_rows,
)


def _row(
    *,
    player="Josh Allen",
    team="BUF",
    opponent="BAL",
    book="DraftKings",
    market="passing_yards",
    label="Passing Yards",
    line=267.5,
    over=100,
    under=-120,
):
    return {
        "event_id": "evt",
        "commence_time": "2026-09-13T00:20:00Z",
        "away_team": team,
        "home_team": opponent,
        "book": book,
        "player": player,
        "market": market,
        "market_label": label,
        "line": line,
        "over_price": over,
        "under_price": under,
    }


def test_player_prop_rows_requires_exact_canonical_player_name():
    rows = (
        _row(player="Josh Allen"),
        _row(player="Josh Allen Over", book="FanDuel"),
        _row(player="Josh Palmer", book="Caesars"),
    )

    matched = player_prop_rows(
        rows,
        player_name="Josh Allen",
        nfl_team="BUF",
    )

    assert len(matched) == 2
    assert {row["book"] for row in matched} == {"DraftKings", "FanDuel"}


def test_player_prop_rows_rejects_abbreviation_team_mismatch():
    rows = (
        _row(player="Josh Allen", team="BUF"),
        _row(player="Josh Allen", team="KC", book="FanDuel"),
    )

    matched = player_prop_rows(
        rows,
        player_name="Josh Allen",
        nfl_team="BUF",
    )

    assert len(matched) == 1
    assert matched[0]["away_team"] == "BUF"


def test_best_price_rows_keeps_best_owner_price_per_exact_line_and_side():
    rows = (
        _row(book="DraftKings", over=100, under=-120),
        _row(book="FanDuel", over=110, under=-115),
        _row(book="Caesars", over=105, under=-110),
        _row(book="BetRivers", over=200, under=200),
    )

    result = build_best_price_rows(rows)

    assert len(result) == 1
    assert result[0].over_book == "FanDuel"
    assert result[0].over_price == 110
    assert result[0].under_book == "Caesars"
    assert result[0].under_price == -110


def test_command_prefers_better_side_price_outlier():
    rows = (
        _row(book="DraftKings", over=180),
        _row(book="FanDuel", over=105),
        _row(book="Caesars", over=100),
    )
    outlier = {
        "actionable": True,
        "book": "DraftKings",
        "player": "Josh Allen",
        "away_team": "BUF",
        "home_team": "BAL",
        "market": "passing_yards",
        "market_label": "Passing Yards",
        "line": 267.5,
        "side": "over",
        "price": 180,
        "peer_median_implied_prob": 0.50,
    }

    action = build_player_prop_action(
        rows,
        price_outliers=(outlier,),
    )

    assert action.action == CHECK
    assert action.book == "DraftKings"
    assert action.side == "OVER"


def test_command_does_not_promote_bad_side_price_outlier():
    rows = (
        _row(book="DraftKings", over=-180),
        _row(book="FanDuel", over=105),
        _row(book="Caesars", over=100),
    )
    outlier = {
        "actionable": True,
        "book": "DraftKings",
        "player": "Josh Allen",
        "away_team": "BUF",
        "home_team": "BAL",
        "market": "passing_yards",
        "market_label": "Passing Yards",
        "line": 267.5,
        "side": "over",
        "price": -180,
        "peer_median_implied_prob": 0.50,
    }

    action = build_player_prop_action(
        rows,
        price_outliers=(outlier,),
    )

    assert action.action == NO_EDGE


def test_command_surfaces_line_shop_before_generic_line_gap():
    rows = (
        _row(book="DraftKings", line=260.5, over=-110, under=None),
        _row(book="FanDuel", line=270.5, over=-105, under=None),
    )

    action = build_player_prop_action(rows)

    assert action.action == SHOP
    assert action.book == "DraftKings"
    assert action.peer_book == "FanDuel"
    assert action.line == 260.5
    assert action.peer_line == 270.5


def test_player_prop_context_summarizes_game_markets_books_and_prices():
    rows = (
        _row(book="DraftKings", market="passing_yards", line=267.5),
        _row(book="FanDuel", market="passing_yards", line=267.5),
        _row(
            book="Caesars",
            market="passing_tds",
            label="Passing TDs",
            line=1.5,
            over=120,
            under=-140,
        ),
    )

    context = build_player_prop_context(
        rows,
        player_name="Josh Allen",
        nfl_team="BUF",
    )

    assert context.games == ("BUF @ BAL",)
    assert context.market_count == 2
    assert context.book_count == 3
    assert len(context.best_prices) == 2


def test_player_prop_rows_accepts_full_team_name_for_exact_current_team():
    rows = (
        _row(
            player="Josh Allen",
            team="Buffalo Bills",
            opponent="Baltimore Ravens",
            book="DraftKings",
        ),
    )

    matched = player_prop_rows(
        rows,
        player_name="Josh Allen",
        nfl_team="BUF",
    )

    assert len(matched) == 1


def test_player_prop_rows_uses_maintained_team_aliases():
    rows = (
        _row(
            player="A Jaguars Player",
            team="Jacksonville Jaguars",
            opponent="Indianapolis Colts",
            book="DraftKings",
        ),
    )

    matched = player_prop_rows(
        rows,
        player_name="A Jaguars Player",
        nfl_team="JAC",
    )

    assert len(matched) == 1


def test_players_page_exposes_owner_command_hook_without_polluting_public_role_source():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    public_source = (
        root / "dashboard" / "pages" / "02_Players.py"
    ).read_text(encoding="utf-8")
    owner_source = (
        root / "dashboard" / "player_command_owner.py"
    ).read_text(encoding="utf-8")

    assert 'page_intro("Player Role Profile"' in public_source
    assert "owner_player_command_available" in public_source
    assert "render_owner_player_command_center" in public_source
    assert "sportsbook" not in public_source.lower()
    assert "betting" not in public_source.lower()
    assert "odds" not in public_source.lower()

    assert '"Player Command Center"' in owner_source
    assert "resolve_propwar_player_to_sleeper" in owner_source
    assert "ROLE/LINE MISMATCH: NOT SCORED" in owner_source
    assert "build_player_intelligence_card" in owner_source
    assert "shared_prop_snapshot" in owner_source

def test_command_ignores_same_name_signal_from_different_event():
    rows = (
        _row(book="DraftKings", team="BUF", opponent="BAL", over=110),
        _row(book="FanDuel", team="BUF", opponent="BAL", over=105),
        _row(book="Caesars", team="BUF", opponent="BAL", over=100),
    )
    wrong_event = {
        "actionable": True,
        "book": "DraftKings",
        "player": "Josh Allen",
        "away_team": "KC",
        "home_team": "LV",
        "market": "passing_yards",
        "market_label": "Passing Yards",
        "line": 267.5,
        "side": "over",
        "price": 250,
        "peer_median_implied_prob": 0.50,
    }

    action = build_player_prop_action(
        rows,
        price_outliers=(wrong_event,),
    )

    assert action.action == NO_EDGE
