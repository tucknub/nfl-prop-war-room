from dashboard.glitch_radar_coverage import actionable_coverage_summary, source_row_counts


def _row(book):
    return {"book": book}


def test_source_row_counts_canonicalizes_configured_books():
    rows = [_row("Hard Rock"), _row("Hard Rock Bet"), _row("FanDuel Sportsbook"), _row("Novig")]
    counts = source_row_counts(rows)
    assert counts["Hard Rock Bet"] == 2
    assert counts["FanDuel"] == 1
    assert counts["Novig"] == 1


def test_actionable_coverage_marks_two_of_five_as_limited():
    rows = [_row("DraftKings")] * 2151 + [_row("Caesars")] * 15 + [_row("Novig")] * 100
    summary = actionable_coverage_summary(rows)
    assert summary["visible_user_books"] == ["DraftKings", "Caesars"]
    assert summary["visible_user_book_count"] == 2
    assert summary["coverage_limited"] is True
    assert summary["dominant_user_book"] == "DraftKings"
    assert summary["dominant_user_book_share"] > 0.99


def test_actionable_coverage_three_books_is_not_limited():
    rows = [_row("DraftKings"), _row("FanDuel"), _row("bet365")]
    summary = actionable_coverage_summary(rows)
    assert summary["visible_user_book_count"] == 3
    assert summary["coverage_limited"] is False


def test_actionable_coverage_tracks_missing_books():
    summary = actionable_coverage_summary([_row("DraftKings")])
    assert summary["missing_user_books"] == ["FanDuel", "Caesars", "bet365", "Hard Rock Bet"]
