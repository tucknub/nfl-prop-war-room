from __future__ import annotations

from typing import Iterable, Mapping

from src.fantasy import league_selector as _league_selector


build_sleeper_league_options = _league_selector.build_sleeper_league_options


def choose_sleeper_league_label(
    options: Mapping[str, str],
    *,
    demo_league_ids: Iterable[str] = (),
    current_label: str = "",
    legacy_label: str = "",
    prefer_real: bool = True,
) -> str:
    """
    Compatibility wrapper for Streamlit rolling reloads.

    Streamlit can keep an already-imported project module in sys.modules while
    re-executing a changed page. If the page starts importing a newly-added
    helper before that dependency module is reloaded, a direct from-import can
    fail even though the deployed source contains the helper.

    Prefer the canonical helper when the live module has it; otherwise apply the
    same small selection rule locally so the page remains available until the
    process performs a cold import.
    """
    helper = getattr(_league_selector, "choose_sleeper_league_label", None)
    if callable(helper):
        return helper(
            options,
            demo_league_ids=demo_league_ids,
            current_label=current_label,
            legacy_label=legacy_label,
            prefer_real=prefer_real,
        )

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
    if legacy in options and (
        not prefer_real or options[legacy] not in demo_ids
    ):
        return legacy

    if prefer_real:
        for label in labels:
            if options[label] not in demo_ids:
                return label

    return labels[0]


__all__ = [
    "build_sleeper_league_options",
    "choose_sleeper_league_label",
]
