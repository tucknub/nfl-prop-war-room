from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

try:
    from glitch_radar_books import USER_BOOKS, canonical_book, is_user_book
    from glitch_radar_line_shop import build_line_shop_watches
    from glitch_radar_props import implied_probability
    from glitch_radar_stale import canonical_player_label
    from src.load.build_identity_crosswalk import TEAM_VARIANTS, canonical_team, normalize_player_name
except ImportError:
    from dashboard.glitch_radar_books import USER_BOOKS, canonical_book, is_user_book
    from dashboard.glitch_radar_line_shop import build_line_shop_watches
    from dashboard.glitch_radar_props import implied_probability
    from dashboard.glitch_radar_stale import canonical_player_label
    from src.load.build_identity_crosswalk import TEAM_VARIANTS, canonical_team, normalize_player_name


_FULL_TEAM_TO_CANONICAL = {
    str(full_name).strip().upper(): canonical
    for _, (canonical, full_name) in TEAM_VARIANTS.items()
    if str(full_name or "").strip()
}


CHECK = "CHECK"
SHOP = "SHOP"
WATCH = "WATCH"
NO_EDGE = "NO EDGE FLAGGED"
NO_MARKET = "NO MARKET"


@dataclass(frozen=True)
class PlayerPropAction:
    action: str
    headline: str
    reason: str
    book: str | None = None
    market: str | None = None
    side: str | None = None
    line: float | None = None
    price: int | None = None
    peer_book: str | None = None
    peer_line: float | None = None
    peer_price: int | None = None


@dataclass(frozen=True)
class PlayerBestPriceRow:
    market: str
    market_label: str
    line: float
    over_book: str | None
    over_price: int | None
    under_book: str | None
    under_price: int | None


@dataclass(frozen=True)
class PlayerPropContext:
    player_name: str
    nfl_team: str
    games: tuple[str, ...]
    market_count: int
    book_count: int
    rows: tuple[dict[str, Any], ...]
    best_prices: tuple[PlayerBestPriceRow, ...]
    action: PlayerPropAction


def _clean_team(value: object) -> str:
    raw = str(value or "").strip().upper()
    if not raw:
        return ""
    if raw in _FULL_TEAM_TO_CANONICAL:
        return _FULL_TEAM_TO_CANONICAL[raw]
    return canonical_team(raw)


def _player_key(value: object) -> str:
    return normalize_player_name(canonical_player_label(value))


def _game(row: Mapping[str, Any]) -> str:
    away = str(row.get("away_team") or "").strip()
    home = str(row.get("home_team") or "").strip()
    if away and home:
        return f"{away} @ {home}"
    return away or home or "NFL game"


def _event_has_team(row: Mapping[str, Any], nfl_team: str) -> bool:
    team = _clean_team(nfl_team)
    if not team or team == "FA":
        return True
    away = _clean_team(row.get("away_team"))
    home = _clean_team(row.get("home_team"))

    return team in {away, home}


def player_prop_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    player_name: str,
    nfl_team: str,
) -> tuple[dict[str, Any], ...]:
    key = _player_key(player_name)
    if not key:
        return ()

    matched = []
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        if _player_key(raw.get("player")) != key:
            continue
        if not _event_has_team(raw, nfl_team):
            continue
        matched.append(dict(raw))
    return tuple(matched)


def build_best_price_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    limit: int = 12,
) -> tuple[PlayerBestPriceRow, ...]:
    groups: dict[tuple[str, float], list[Mapping[str, Any]]] = {}
    labels: dict[tuple[str, float], str] = {}

    for row in rows:
        if not is_user_book(row.get("book")):
            continue
        try:
            line = float(row.get("line"))
        except (TypeError, ValueError):
            continue
        market = str(row.get("market") or "").strip()
        if not market:
            continue
        key = (market, line)
        groups.setdefault(key, []).append(row)
        labels[key] = str(row.get("market_label") or market.replace("_", " ").title())

    result: list[PlayerBestPriceRow] = []
    for (market, line), group in groups.items():
        over = _best_side(group, "over")
        under = _best_side(group, "under")
        result.append(
            PlayerBestPriceRow(
                market=market,
                market_label=labels[(market, line)],
                line=line,
                over_book=over[0] if over else None,
                over_price=over[1] if over else None,
                under_book=under[0] if under else None,
                under_price=under[1] if under else None,
            )
        )

    result.sort(key=lambda row: (row.market_label.casefold(), row.line))
    return tuple(result[: max(0, int(limit))])


def _best_side(
    rows: Iterable[Mapping[str, Any]],
    side: str,
) -> tuple[str, int] | None:
    candidates: list[tuple[str, int]] = []
    for row in rows:
        try:
            price = int(float(row.get(f"{side}_price")))
        except (TypeError, ValueError):
            continue
        if price == 0:
            continue
        book = canonical_book(row.get("book"))
        if not book:
            continue
        candidates.append((book, price))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[1])


def build_player_prop_action(
    rows: Iterable[Mapping[str, Any]],
    *,
    price_outliers: Iterable[Mapping[str, Any]] = (),
    line_gaps: Iterable[Mapping[str, Any]] = (),
    ladder_violations: Iterable[Mapping[str, Any]] = (),
) -> PlayerPropAction:
    rows = tuple(dict(row) for row in rows if isinstance(row, Mapping))
    if not rows:
        return PlayerPropAction(
            action=NO_MARKET,
            headline="No current player-prop rows",
            reason="The shared deep-prop snapshot returned no matching market rows for this player.",
        )

    player_key = _player_key(rows[0].get("player"))

    actionable_outliers = []
    for raw in price_outliers:
        if not isinstance(raw, Mapping) or _player_key(raw.get("player")) != player_key:
            continue
        if not raw.get("actionable"):
            continue
        try:
            price = int(float(raw.get("price")))
            peer_prob = float(raw.get("peer_median_implied_prob"))
            own_prob = implied_probability(price)
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        # Only surface anomalies where the owner's book is offering the better
        # payout/lower implied probability. Bad-side outliers are not opportunities.
        if own_prob >= peer_prob:
            continue
        actionable_outliers.append((peer_prob - own_prob, dict(raw)))

    if actionable_outliers:
        actionable_outliers.sort(key=lambda item: item[0], reverse=True)
        row = actionable_outliers[0][1]
        line = _float(row.get("line"))
        price = _int(row.get("price"))
        side = str(row.get("side") or "").upper() or None
        market = str(row.get("market_label") or row.get("market") or "prop")
        return PlayerPropAction(
            action=CHECK,
            headline=f"Price anomaly · {row.get('book')} {side or ''} {line:g}" if line is not None else "Price anomaly",
            reason="This configured-book price is materially better than the exact same player/market/line peer median. Verify settlement rules before betting.",
            book=str(row.get("book") or "") or None,
            market=market,
            side=side,
            line=line,
            price=price,
        )

    line_shop = build_line_shop_watches(rows, limit=20)
    if line_shop:
        row = line_shop[0]
        return PlayerPropAction(
            action=SHOP,
            headline=(
                f"Easier {str(row.get('side') or '').upper()} line at {row.get('book')}"
            ),
            reason=(
                f"{float(row.get('line_advantage') or 0):g}-point threshold advantage "
                f"for only {float(row.get('price_cost_points') or 0):+.2f} implied-probability points versus the comparison price."
            ),
            book=str(row.get("book") or "") or None,
            market=str(row.get("market_label") or row.get("market") or "prop"),
            side=str(row.get("side") or "").upper() or None,
            line=_float(row.get("book_line")),
            price=_int(row.get("book_price")),
            peer_book=str(row.get("peer_book") or "") or None,
            peer_line=_float(row.get("peer_line")),
            peer_price=_int(row.get("peer_price")),
        )

    player_ladders = [
        dict(row)
        for row in ladder_violations
        if isinstance(row, Mapping) and _player_key(row.get("player")) == player_key
    ]
    if player_ladders:
        row = player_ladders[0]
        return PlayerPropAction(
            action=CHECK,
            headline=f"Inverted alternate ladder · {row.get('book')}",
            reason="A harder OVER threshold is priced more likely than an easier threshold. Verify immediately before treating it as actionable.",
            book=str(row.get("book") or "") or None,
            market=str(row.get("market_label") or row.get("market") or "prop"),
            side="OVER",
            line=_float(row.get("harder_line")),
            price=_int(row.get("harder_over_price")),
        )

    player_gaps = [
        dict(row)
        for row in line_gaps
        if isinstance(row, Mapping) and _player_key(row.get("player")) == player_key
    ]
    if player_gaps:
        row = player_gaps[0]
        return PlayerPropAction(
            action=SHOP,
            headline=f"{float(row.get('line_gap') or 0):g}-point cross-book line gap",
            reason="Configured books disagree materially on the threshold. Compare the easier side and exact prices before betting.",
            book=str(row.get("low_book") or "") or None,
            market=str(row.get("market_label") or row.get("market") or "prop"),
            line=_float(row.get("low_line")),
            peer_book=str(row.get("high_book") or "") or None,
            peer_line=_float(row.get("high_line")),
        )

    return PlayerPropAction(
        action=NO_EDGE,
        headline="Live markets found; no structural edge flagged",
        reason="The current shared snapshot has player props, but no better-side glitch, line-shop watch, ladder inversion, or material configured-book line gap surfaced.",
    )


def build_player_prop_context(
    rows: Iterable[Mapping[str, Any]],
    *,
    player_name: str,
    nfl_team: str,
    price_outliers: Iterable[Mapping[str, Any]] = (),
    line_gaps: Iterable[Mapping[str, Any]] = (),
    ladder_violations: Iterable[Mapping[str, Any]] = (),
) -> PlayerPropContext:
    matched = player_prop_rows(
        rows,
        player_name=player_name,
        nfl_team=nfl_team,
    )
    games = tuple(dict.fromkeys(_game(row) for row in matched))
    markets = {
        str(row.get("market") or "")
        for row in matched
        if str(row.get("market") or "").strip()
    }
    books = {
        canonical_book(row.get("book"))
        for row in matched
        if canonical_book(row.get("book"))
    }
    return PlayerPropContext(
        player_name=player_name,
        nfl_team=nfl_team,
        games=games,
        market_count=len(markets),
        book_count=len(books),
        rows=matched,
        best_prices=build_best_price_rows(matched),
        action=build_player_prop_action(
            matched,
            price_outliers=price_outliers,
            line_gaps=line_gaps,
            ladder_violations=ladder_violations,
        ),
    )


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: object) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


__all__ = [
    "CHECK",
    "SHOP",
    "WATCH",
    "NO_EDGE",
    "NO_MARKET",
    "PlayerBestPriceRow",
    "PlayerPropAction",
    "PlayerPropContext",
    "build_best_price_rows",
    "build_player_prop_action",
    "build_player_prop_context",
    "player_prop_rows",
]
