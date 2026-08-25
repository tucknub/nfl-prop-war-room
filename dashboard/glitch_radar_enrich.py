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
        if row.get("market"):
            enriched.append(row)
            continue

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
            row["market"] = match.get("market")
            row["threshold"] = match.get("threshold")
        elif side_name in {home, away}:
            # Current no-auth EV preview is overwhelmingly h2h. Only use this fallback
            # when the EV side is an exact team name, never for generic Over/Under sides.
            row["market"] = "moneyline"
            row["threshold"] = None

        enriched.append(row)

    return enriched
