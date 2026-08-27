from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping


MARKET = "MARKET"
FANTASY = "FANTASY"
ROLE = "ROLE"
MARGIN = "MARGIN"

HIGH = "HIGH"
MEDIUM = "MEDIUM"
LOW = "LOW"

_CATEGORY_ORDER = {
    MARKET: 0,
    FANTASY: 1,
    ROLE: 2,
    MARGIN: 3,
}
_PRIORITY_ORDER = {
    HIGH: 0,
    MEDIUM: 1,
    LOW: 2,
}


@dataclass(frozen=True)
class TodayAction:
    category: str
    priority: str
    title: str
    action: str
    why: str
    confidence: str
    freshness: str
    href: str
    score: float
    source: str

    @property
    def dedupe_key(self) -> tuple[str, str, str]:
        return (
            self.category.strip().upper(),
            self.title.strip().casefold(),
            self.href.strip(),
        )


def rank_today_actions(
    actions: Iterable[TodayAction],
    *,
    limit: int = 6,
    category_caps: Mapping[str, int] | None = None,
) -> tuple[TodayAction, ...]:
    """Rank a concise cross-product action feed with deliberate category diversity.

    One best action from each available category is considered first. Remaining
    slots are filled by score while respecting per-category caps. This prevents a
    large action-producing module from swallowing the whole homepage.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 12:
        raise ValueError("limit must be an integer from 1 to 12")

    caps = {
        MARKET: 2,
        FANTASY: 2,
        ROLE: 1,
        MARGIN: 1,
    }
    if category_caps is not None:
        for category, value in category_caps.items():
            normalized = str(category or "").strip().upper()
            if not normalized:
                continue
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError("category cap values must be non-negative integers")
            caps[normalized] = value

    deduped: dict[tuple[str, str, str], TodayAction] = {}
    for action in actions:
        if not isinstance(action, TodayAction):
            continue
        category = action.category.strip().upper()
        if not category or caps.get(category, 1) <= 0:
            continue
        incumbent = deduped.get(action.dedupe_key)
        if incumbent is None or _sort_key(action) < _sort_key(incumbent):
            deduped[action.dedupe_key] = action

    ranked = sorted(deduped.values(), key=_sort_key)
    if not ranked:
        return ()

    selected: list[TodayAction] = []
    selected_keys: set[tuple[str, str, str]] = set()
    counts: dict[str, int] = {}

    # First preserve product diversity with one top action per available category.
    categories = sorted(
        {row.category.strip().upper() for row in ranked},
        key=lambda value: _CATEGORY_ORDER.get(value, 99),
    )
    for category in categories:
        if len(selected) >= limit:
            break
        cap = caps.get(category, 1)
        if cap <= 0:
            continue
        candidate = next(
            (
                row
                for row in ranked
                if row.category.strip().upper() == category
            ),
            None,
        )
        if candidate is None:
            continue
        selected.append(candidate)
        selected_keys.add(candidate.dedupe_key)
        counts[category] = 1

    # Then fill the remaining slots by actual action score.
    for action in ranked:
        if len(selected) >= limit:
            break
        if action.dedupe_key in selected_keys:
            continue
        category = action.category.strip().upper()
        if counts.get(category, 0) >= caps.get(category, 1):
            continue
        selected.append(action)
        selected_keys.add(action.dedupe_key)
        counts[category] = counts.get(category, 0) + 1

    # Final display order is the global score, not the category seeding order.
    selected.sort(key=_sort_key)
    return tuple(selected[:limit])


def _sort_key(action: TodayAction) -> tuple[float, int, int, str]:
    return (
        -float(action.score),
        _PRIORITY_ORDER.get(action.priority.strip().upper(), 99),
        _CATEGORY_ORDER.get(action.category.strip().upper(), 99),
        action.title.casefold(),
    )


__all__ = [
    "FANTASY",
    "HIGH",
    "LOW",
    "MARGIN",
    "MARKET",
    "MEDIUM",
    "ROLE",
    "TodayAction",
    "rank_today_actions",
]
