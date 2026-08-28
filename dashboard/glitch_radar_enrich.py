from __future__ import annotations

from typing import Any, Iterable


def _event_teams(row: dict[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("away_team") or "").strip().lower(),
        str(row.get("home_team") or "").strip().lower(),
    )


def enrich_ev_markets(rows: Iterable[dict[str, Any]], quotes: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach market/threshold identity to EV rows by matching them back to the odds preview."""
    quote_rows = [q for q in quotes if isinstance(q, dict)]
    enriched: list[dict[str, Any]] = []

    for raw in rows:
        if not isinstance(raw, dict):
            continue
        row = dict(raw)

        away, home = _event_teams(row)
        event = f"{away} @ {home}".strip(" @")
        book = str(row.get("book") or "").strip().lower()
        side_name = str(row.get("side") or "").strip().lower()
        try:
            price = int(float(row.get("price")))
        except (TypeError, ValueError):
            price = None

        side_tokens = {side_name}
        if side_name == home and home:
            side_tokens.add("home")
        if side_name == away and away:
            side_tokens.add("away")

        matches = []
        for quote in quote_rows:
            if str(quote.get("event") or "").strip().lower() != event:
                continue
            if str(quote.get("book") or "").strip().lower() != book:
                continue
            if price is not None:
                try:
                    if int(float(quote.get("odds_american"))) != price:
                        continue
                except (TypeError, ValueError):
                    continue
            qside = str(quote.get("side") or "").strip().lower()
            participant = str(quote.get("participant") or "").strip().lower()
            if qside not in side_tokens and participant not in side_tokens:
                continue
            matches.append(quote)

        if len(matches) == 1:
            match = matches[0]
            if not row.get("market"):
                row["market"] = match.get("market")
            if row.get("threshold") is None:
                row["threshold"] = match.get("threshold")
            if not row.get("commence_time") and match.get("commence_time"):
                row["commence_time"] = match.get("commence_time")
        elif not row.get("market") and side_name in {home, away}:
            # Current no-auth EV preview is overwhelmingly h2h. Only use this fallback
            # when the EV side is an exact team name, never for generic Over/Under sides.
            row["market"] = "moneyline"
            row["threshold"] = None

        enriched.append(row)

    return enriched
