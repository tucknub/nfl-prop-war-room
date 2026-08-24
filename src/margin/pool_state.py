from __future__ import annotations

import csv
import math
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

from . import championship


_SPLIT_RE = re.compile(r"[|,;/\s]+")


def parse_used_teams(value: Any) -> list[str]:
    """Normalize a field export's used-team inventory into canonical NFL abbreviations."""
    if value is None:
        raw: list[Any] = []
    elif isinstance(value, (list, tuple, set)):
        raw = list(value)
    else:
        text = str(value).strip()
        raw = [] if not text else [x for x in _SPLIT_RE.split(text) if x]

    teams = [championship.canon_team(x) for x in raw]
    if len(teams) != len(set(teams)):
        raise ValueError(f"used_teams contains duplicates: {teams}")
    invalid = sorted(set(teams) - championship.VALID_TEAMS)
    if invalid:
        raise ValueError(f"used_teams contains invalid teams: {invalid}")
    return teams


def _finite_score(value: Any, *, row_id: str) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{row_id}: cumulative_score must be numeric") from exc
    if not math.isfinite(score):
        raise ValueError(f"{row_id}: cumulative_score must be finite")
    return score


def normalize_opponents(rows: Iterable[dict[str, Any]], completed_week: int) -> list[dict[str, Any]]:
    """Validate a complete opponent snapshot before it can enter live state."""
    normalized: list[dict[str, Any]] = []
    ids: list[str] = []
    for index, row in enumerate(rows):
        row_id = str(row.get("id", "")).strip()
        if not row_id:
            raise ValueError(f"row {index + 1}: id is required")
        ids.append(row_id)

        name = str(row.get("name", "")).strip() or row_id
        used = parse_used_teams(row.get("used_teams"))
        if len(used) != int(completed_week):
            raise ValueError(
                f"{row_id}: used_teams count {len(used)} must equal completed_week {completed_week}"
            )

        normalized.append(
            {
                "id": row_id,
                "name": name,
                "cumulative_score": _finite_score(row.get("cumulative_score"), row_id=row_id),
                "used_teams": used,
            }
        )

    if len(ids) != len(set(ids)):
        raise ValueError("opponent ids must be unique")
    return normalized


def load_field_csv(path: str | Path, completed_week: int) -> list[dict[str, Any]]:
    """Load the canonical CSV export used for weekly pool standings/inventory updates."""
    csv_path = Path(path)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"id", "name", "cumulative_score", "used_teams"}
        headers = set(reader.fieldnames or [])
        missing = sorted(required - headers)
        if missing:
            raise ValueError(f"field CSV missing columns: {missing}")
        return normalize_opponents(list(reader), completed_week)


def apply_pool_snapshot(
    state: dict[str, Any],
    opponents: Iterable[dict[str, Any]],
    *,
    pool_name: str | None = None,
    first_place_tie_rule: str | None = None,
    pick_deadline: str | None = None,
    picks_visible_before_deadline: bool | None = None,
    explicit_pool_size: int | None = None,
    payout_structure: str = "winner_take_all",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply one all-or-nothing field snapshot and return championship readiness.

    The hero's score/history/inventory are never inferred from the field export.
    Pool size is inferred from the complete opponent list and may be cross-checked
    against an explicit size. Missing tie/deadline metadata remains missing rather
    than being guessed, so championship simulation stays fail-closed.
    """
    updated = deepcopy(state)
    completed_week = int(updated.get("completed_week", 0) or 0)
    normalized = normalize_opponents(opponents, completed_week)
    inferred_pool_size = len(normalized) + 1

    if explicit_pool_size is not None and int(explicit_pool_size) != inferred_pool_size:
        raise ValueError(
            f"pool size mismatch: explicit {explicit_pool_size}, field implies {inferred_pool_size}"
        )

    pool = dict(updated.get("pool") or {})
    pool["size"] = inferred_pool_size
    pool["payout_structure"] = payout_structure
    if pool_name is not None:
        pool["name"] = pool_name
    if first_place_tie_rule is not None:
        tie_rule = str(first_place_tie_rule).strip().lower()
        if tie_rule not in championship.SUPPORTED_TIE_RULES:
            raise ValueError("first_place_tie_rule must be 'split' or 'shared'")
        pool["first_place_tie_rule"] = tie_rule
    if pick_deadline is not None:
        pool["pick_deadline"] = pick_deadline
    if picks_visible_before_deadline is not None:
        pool["picks_visible_before_deadline"] = bool(picks_visible_before_deadline)

    updated["pool"] = pool
    updated["opponents"] = normalized
    readiness = championship.championship_readiness(updated)
    return updated, readiness
