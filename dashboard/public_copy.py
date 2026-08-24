from __future__ import annotations

from research_data import load_operational_status


def role_home_copy() -> dict[str, str]:
    status = load_operational_status()
    state = str(status.get("status") or "UNKNOWN")
    published_week = status.get("published_through_week")
    if state == "PUBLISHED" and published_week is not None:
        return {
            "hero_title": "What changed in NFL roles?",
            "hero_description": "Start with the latest published role changes, then inspect the player counts, team totals, and supporting evidence behind them.",
            "page_title": "This Week in NFL Roles",
            "page_description": "Start with the clearest usage changes, then open the supporting player and team evidence.",
        }
    return {
        "hero_title": "Latest NFL role research",
        "hero_description": "Browse the latest validated role report, then inspect the player counts, team totals, and supporting evidence behind it.",
        "page_title": "Latest NFL Role Research",
        "page_description": "The latest completed role data is shown here until a new current-season week passes the publication gates.",
    }
