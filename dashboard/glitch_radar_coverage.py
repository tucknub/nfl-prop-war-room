from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

try:
    from glitch_radar_books import USER_BOOKS, canonical_book
except ImportError:  # package import path used by pytest
    from dashboard.glitch_radar_books import USER_BOOKS, canonical_book


def source_row_counts(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        if not isinstance(row, dict):
            continue
        book = canonical_book(row.get("book"))
        if book:
            counts[book] += 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0].casefold())))


def actionable_coverage_summary(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    counts = source_row_counts(rows)
    user_counts = {book: int(counts.get(book, 0) or 0) for book in USER_BOOKS}
    visible = [book for book in USER_BOOKS if user_counts[book] > 0]
    missing = [book for book in USER_BOOKS if user_counts[book] <= 0]
    user_total = sum(user_counts.values())

    dominant_book = None
    dominant_rows = 0
    if visible:
        dominant_book = max(visible, key=lambda book: user_counts[book])
        dominant_rows = user_counts[dominant_book]
    dominant_share = dominant_rows / user_total if user_total else 0.0

    # With fewer than three of the configured books represented, a zero-signal result should
    # not be described as a market-wide all-clear for the owner's five-book workflow.
    limited = len(visible) < 3

    return {
        "source_counts": counts,
        "user_counts": user_counts,
        "visible_user_books": visible,
        "missing_user_books": missing,
        "visible_user_book_count": len(visible),
        "user_book_total_rows": user_total,
        "dominant_user_book": dominant_book,
        "dominant_user_book_rows": dominant_rows,
        "dominant_user_book_share": dominant_share,
        "coverage_limited": limited,
    }


__all__ = ["actionable_coverage_summary", "source_row_counts"]
