from dashboard.glitch_radar_books import (
    USER_BOOKS,
    canonical_book,
    comparison_books_seen,
    filter_actionable_alerts,
    filter_actionable_ev,
    filter_actionable_two_leg,
    is_user_book,
    user_books_seen,
)


def test_user_book_roster_is_exact():
    assert USER_BOOKS == (
        "FanDuel",
        "DraftKings",
        "Caesars",
        "bet365",
        "Hard Rock Bet",
    )


def test_common_aliases_canonicalize_to_user_books():
    assert canonical_book("FanDuel Sportsbook") == "FanDuel"
    assert canonical_book("DraftKings Sportsbook") == "DraftKings"
    assert canonical_book("Caesars Sportsbook") == "Caesars"
    assert canonical_book("BET365") == "bet365"
    assert canonical_book("Hard Rock") == "Hard Rock Bet"
    assert all(is_user_book(book) for book in USER_BOOKS)
    assert not is_user_book("BetRivers")
    assert not is_user_book("Pinnacle")


def test_alerts_only_surface_when_mispriced_quote_is_at_user_book():
    rows = [
        {"severity": "P0", "quote": {"book": "BetRivers"}},
        {"severity": "P0", "quote": {"book": "FanDuel"}},
    ]
    assert filter_actionable_alerts(rows) == [rows[1]]


def test_ev_can_use_sharp_anchor_but_bet_must_be_at_user_book():
    rows = [
        {"book": "Hard Rock Bet", "sharp_anchor": "pinnacle"},
        {"book": "BetRivers", "sharp_anchor": "pinnacle"},
    ]
    assert filter_actionable_ev(rows) == [rows[0]]


def test_arbs_and_middles_require_both_legs_at_user_books():
    valid = {
        "over": {"book": "DraftKings", "line": 47.5},
        "under": {"book": "FanDuel", "line": 49.5},
    }
    invalid_reference_leg = {
        "over": {"book": "Pinnacle", "line": 47.5},
        "under": {"book": "FanDuel", "line": 49.5},
    }
    invalid_unused_leg = {
        "over": {"book": "BetRivers", "line": 47.5},
        "under": {"book": "DraftKings", "line": 49.5},
    }
    assert filter_actionable_two_leg([valid, invalid_reference_leg, invalid_unused_leg]) == [valid]


def test_source_lists_separate_actionable_and_comparison_books():
    books = ["Pinnacle", "BetRivers", "FanDuel", "Hard Rock", "DraftKings"]
    assert user_books_seen(books) == ["FanDuel", "DraftKings", "Hard Rock Bet"]
    assert comparison_books_seen(books) == ["Pinnacle", "BetRivers"]
