from dashboard.propwar_today import (
    FANTASY,
    HIGH,
    MARGIN,
    MARKET,
    MEDIUM,
    ROLE,
    TodayAction,
    rank_today_actions,
)


def _action(
    category,
    title,
    score,
    *,
    priority=HIGH,
    href="/x",
):
    return TodayAction(
        category=category,
        priority=priority,
        title=title,
        action="Do it",
        why="Evidence",
        confidence="HIGH",
        freshness="Now",
        href=href + "/" + title.replace(" ", "-"),
        score=score,
        source=category,
    )


def test_today_preserves_category_diversity_before_filling_by_score():
    actions = [
        _action(FANTASY, "Fantasy 1", 500),
        _action(FANTASY, "Fantasy 2", 490),
        _action(FANTASY, "Fantasy 3", 480),
        _action(MARKET, "Market 1", 470),
        _action(ROLE, "Role 1", 300),
        _action(MARGIN, "Margin 1", 290),
    ]

    ranked = rank_today_actions(actions, limit=6)

    categories = [row.category for row in ranked]
    assert categories.count(FANTASY) == 2
    assert MARKET in categories
    assert ROLE in categories
    assert MARGIN in categories
    assert len(ranked) == 5


def test_today_respects_default_category_caps():
    actions = [
        _action(MARKET, f"Market {index}", 500 - index)
        for index in range(5)
    ] + [
        _action(FANTASY, f"Fantasy {index}", 400 - index)
        for index in range(5)
    ]

    ranked = rank_today_actions(actions, limit=6)

    assert len(ranked) == 4
    assert sum(row.category == MARKET for row in ranked) == 2
    assert sum(row.category == FANTASY for row in ranked) == 2


def test_today_dedupes_same_source_action_and_keeps_higher_score():
    low = _action(MARKET, "Same", 200)
    high = TodayAction(
        category=low.category,
        priority=MEDIUM,
        title=low.title,
        action=low.action,
        why="Better evidence",
        confidence=low.confidence,
        freshness=low.freshness,
        href=low.href,
        score=350,
        source=low.source,
    )

    ranked = rank_today_actions((low, high))

    assert len(ranked) == 1
    assert ranked[0].score == 350
    assert ranked[0].why == "Better evidence"


def test_today_rejects_invalid_limit():
    import pytest

    with pytest.raises(ValueError):
        rank_today_actions((), limit=0)
