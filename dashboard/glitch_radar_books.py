from __future__ import annotations

from typing import Any, Iterable

try:
    from glitch_radar_grouping import group_ev_wagers
except ImportError:  # package import path used by pytest
    from dashboard.glitch_radar_grouping import group_ev_wagers


USER_BOOKS: tuple[str, ...] = (
    "FanDuel",
    "DraftKings",
    "Caesars",
    "bet365",
    "Hard Rock Bet",
)

# These are useful price-discovery anchors when the feed supplies them. They are
# not treated as places the owner can actually place a bet.
PREFERRED_REFERENCE_BOOKS: tuple[str, ...] = (
    "Pinnacle",
    "Circa Sports",
)


def _token(value: object) -> str:
    return "".join(character for character in str(value or "").lower() if character.isalnum())


_BOOK_ALIASES: dict[str, str] = {
    "fanduel": "FanDuel",
    "fanduelsportsbook": "FanDuel",
    "draftkings": "DraftKings",
    "draftkingssportsbook": "DraftKings",
    "caesars": "Caesars",
    "caesarssportsbook": "Caesars",
    "bet365": "bet365",
    "hardrock": "Hard Rock Bet",
    "hardrockbet": "Hard Rock Bet",
    "hardrocksportsbook": "Hard Rock Bet",
    "pinnacle": "Pinnacle",
    "pinnaclesports": "Pinnacle",
    "circa": "Circa Sports",
    "circasports": "Circa Sports",
}

_USER_TOKENS = {_token(book) for book in USER_BOOKS}


def canonical_book(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    return _BOOK_ALIASES.get(_token(raw), raw)


def is_user_book(value: object) -> bool:
    return _token(canonical_book(value)) in _USER_TOKENS


def user_books_seen(books: Iterable[object]) -> list[str]:
    seen = {canonical_book(book) for book in books if is_user_book(book)}
    return [book for book in USER_BOOKS if book in seen]


def comparison_books_seen(books: Iterable[object]) -> list[str]:
    seen = {canonical_book(book) for book in books if canonical_book(book) and not is_user_book(book)}
    preferred = [book for book in PREFERRED_REFERENCE_BOOKS if book in seen]
    others = sorted(seen.difference(preferred))
    return preferred + others


def filter_actionable_alerts(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    actionable: list[dict[str, Any]] = []
    for row in rows:
        quote = row.get("quote", {}) if isinstance(row, dict) else {}
        if isinstance(quote, dict) and is_user_book(quote.get("book")):
            actionable.append(row)
    return actionable


def filter_actionable_ev(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep +EV recommendations at the owner's books and collapse duplicate wager choices.

    The fair-value/sharp anchor may still be Pinnacle or another comparison source. If the
    same underlying wager is +EV at multiple owner books, only the best price is returned;
    the other prices are retained on the row as alternate_books.
    """
    actionable = [dict(row) for row in rows if isinstance(row, dict) and is_user_book(row.get("book"))]
    return group_ev_wagers(actionable)


def _book_values(value: Any, *, parent_key: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_token = _token(key)
            if isinstance(child, str) and key_token in {
                "book",
                "bookmaker",
                "sportsbook",
                "operator",
                "overbook",
                "underbook",
                "homebook",
                "awaybook",
            }:
                found.append(canonical_book(child))
            else:
                found.extend(_book_values(child, parent_key=str(key)))
    elif isinstance(value, (list, tuple)):
        for child in value:
            found.extend(_book_values(child, parent_key=parent_key))
    return [book for book in found if book]


def filter_actionable_two_leg(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep arbs/middles only when every required sportsbook leg is bettable by the owner."""
    actionable: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        books = _book_values(row)
        distinct = {canonical_book(book) for book in books}
        if len(distinct) >= 2 and all(is_user_book(book) for book in distinct):
            actionable.append(row)
    return actionable
