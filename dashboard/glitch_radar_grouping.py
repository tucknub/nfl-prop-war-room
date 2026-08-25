from __future__ import annotations

from typing import Any, Iterable

from glitch_radar_present import expected_ev_pct


def wager_key(row: dict[str, Any]) -> tuple[str, str, str, object]:
    """Identity for the underlying wager, intentionally excluding sportsbook/price."""
    away = str(row.get("away_team") or "").strip().lower()
    home = str(row.get("home_team") or "").strip().lower()
    event = str(row.get("event") or "").strip().lower()
    game = f"{away}@{home}" if away or home else event
    market = str(row.get("market") or "moneyline").strip().lower()
    side = str(row.get("side") or "").strip().lower()
    threshold = row.get("threshold")
    return game, market, side, threshold


def market_label(row: dict[str, Any]) -> str:
    market = str(row.get("market") or "moneyline").strip().lower()
    if market in {"moneyline", "h2h"}:
        return "ML"
    if market in {"spread", "spreads"}:
        threshold = row.get("threshold")
        if threshold is None:
            return "Spread"
        try:
            value = float(threshold)
            return f"Spread {value:+g}"
        except (TypeError, ValueError):
            return f"Spread {threshold}"
    if market in {"game_total", "total", "totals"}:
        threshold = row.get("threshold")
        side = str(row.get("selection") or row.get("side") or "").strip().title()
        if threshold is None:
            return f"{side} Total".strip()
        return f"{side} {threshold}".strip()
    return market.replace("_", " ").title()


def group_ev_wagers(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse the same wager across books, keeping the best actionable price first."""
    groups: dict[tuple[str, str, str, object], list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized = dict(row)
        normalized.setdefault("market", "moneyline")
        normalized.setdefault("threshold", None)
        groups.setdefault(wager_key(normalized), []).append(normalized)

    grouped: list[dict[str, Any]] = []
    for options in groups.values():
        options.sort(
            key=lambda row: (
                expected_ev_pct(row.get("price"), row.get("fair_prob_pct")) or -999,
                float(row.get("price")) if row.get("price") is not None else -99999,
            ),
            reverse=True,
        )
        best = dict(options[0])
        original_side = str(best.get("side") or "Bet").strip()
        best["selection"] = original_side
        best["alternate_books"] = [
            {
                "book": option.get("book"),
                "price": option.get("price"),
                "estimated_ev_pct": expected_ev_pct(option.get("price"), option.get("fair_prob_pct")),
            }
            for option in options[1:]
        ]
        best["book_count"] = len(options)

        display = f"{original_side} {market_label(best)}".strip()
        if best["alternate_books"]:
            alternatives = ", ".join(
                f"{alt.get('book')} {int(float(alt.get('price'))):+d}"
                for alt in best["alternate_books"]
                if alt.get("book") and alt.get("price") is not None
            )
            if alternatives:
                display += f" — alt {alternatives}"
        best["side"] = display
        grouped.append(best)

    grouped.sort(
        key=lambda row: expected_ev_pct(row.get("price"), row.get("fair_prob_pct")) or -999,
        reverse=True,
    )
    return grouped
