from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping


def build_sleeper_league_options(
    leagues: Iterable[Mapping[str, Any]],
) -> tuple[tuple[str, str], ...]:
    rows = [
        dict(row)
        for row in leagues
        if str(row.get("league_id") or "").strip()
    ]
    base_labels = [
        _base_label(row)
        for row in rows
    ]
    counts = Counter(base_labels)

    options: list[tuple[str, str]] = []
    for row, base in zip(rows, base_labels):
        league_id = str(row.get("league_id") or "").strip()
        if counts[base] == 1:
            label = base
        else:
            status = (
                str(row.get("status") or "unknown")
                .replace("_", " ")
                .strip()
                .title()
            )
            label = f"{base} · {status} · …{league_id[-6:]}"
        options.append((label, league_id))

    return tuple(options)



def choose_sleeper_league_label(
    options: Mapping[str, str],
    *,
    demo_league_ids: Iterable[str] = (),
    current_label: str = "",
    legacy_label: str = "",
    prefer_real: bool = True,
) -> str:
    labels = tuple(options)
    if not labels:
        return ""

    current = str(current_label or "").strip()
    if current in options:
        return current

    demo_ids = {
        str(value).strip()
        for value in demo_league_ids
        if str(value or "").strip()
    }
    legacy = str(legacy_label or "").strip()
    if legacy in options:
        if not prefer_real or options[legacy] not in demo_ids:
            return legacy

    if prefer_real:
        for label in labels:
            if options[label] not in demo_ids:
                return label

    return labels[0]

def _base_label(row: Mapping[str, Any]) -> str:
    name = str(row.get("name") or "Unnamed league").strip() or "Unnamed league"
    teams = row.get("total_rosters")
    teams_text = str(teams) if teams not in (None, "") else "?"
    return f"{name} · {teams_text} teams"


__all__ = ["build_sleeper_league_options", "choose_sleeper_league_label"]
