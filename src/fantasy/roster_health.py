from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Mapping

from .models import FantasyLeagueState, Roster


PRE_DRAFT = "PRE_DRAFT"
READY = "READY"
WATCH = "WATCH"
NEEDS_ATTENTION = "NEEDS_ATTENTION"

CRITICAL = "CRITICAL"
WARNING = "WARNING"
INFO = "INFO"

DIRECT_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DEF"}
FLEX_SLOTS = {
    "FLEX",
    "REC_FLEX",
    "WRRB_FLEX",
    "WRRBTE_FLEX",
}
FLEX_ELIGIBLE = {"RB", "WR", "TE"}
SERIOUS_STATUSES = {
    "out",
    "ir",
    "pup",
    "suspended",
    "doubtful",
}
QUESTIONABLE_STATUSES = {"questionable", "q"}


@dataclass(frozen=True)
class RosterHealthIssue:
    severity: str
    code: str
    message: str
    position: str | None = None
    player_id: str | None = None
    player_name: str | None = None


@dataclass(frozen=True)
class RosterHealthSummary:
    status: str
    roster_size: int
    starter_slots: int
    filled_starter_slots: int
    open_starter_slots: int
    position_counts: Mapping[str, int]
    issues: tuple[RosterHealthIssue, ...]

    @property
    def critical_count(self) -> int:
        return sum(1 for row in self.issues if row.severity == CRITICAL)

    @property
    def warning_count(self) -> int:
        return sum(1 for row in self.issues if row.severity == WARNING)


def analyze_roster_health(
    league: FantasyLeagueState,
    player_catalog: Mapping[str, Mapping[str, Any]],
) -> RosterHealthSummary:
    roster = _my_roster(league)
    if roster is None:
        return RosterHealthSummary(
            status=PRE_DRAFT,
            roster_size=0,
            starter_slots=len(league.rules.starter_positions),
            filled_starter_slots=0,
            open_starter_slots=len(league.rules.starter_positions),
            position_counts={},
            issues=(
                RosterHealthIssue(
                    severity=INFO,
                    code="MY_ROSTER_NOT_FOUND",
                    message="Your roster is not populated in this league yet.",
                ),
            ),
        )

    player_ids = tuple(
        player_id
        for player_id in roster.players
        if str(player_id or "").strip() not in {"", "0"}
    )
    starter_slots = len(league.rules.starter_positions)
    filled_starters = sum(
        1
        for player_id in roster.starters
        if str(player_id or "").strip() not in {"", "0"}
    )
    open_starters = max(0, starter_slots - filled_starters)

    if not player_ids:
        return RosterHealthSummary(
            status=PRE_DRAFT,
            roster_size=0,
            starter_slots=starter_slots,
            filled_starter_slots=filled_starters,
            open_starter_slots=open_starters,
            position_counts={},
            issues=(
                RosterHealthIssue(
                    severity=INFO,
                    code="ROSTER_EMPTY",
                    message="This Sleeper roster is still empty.",
                ),
            ),
        )

    positions = Counter()
    for player_id in player_ids:
        player = player_catalog.get(player_id) or {}
        position = str(player.get("position") or "").strip().upper()
        if position:
            positions[position] += 1

    issues: list[RosterHealthIssue] = []

    direct_requirements = Counter(
        slot
        for slot in league.rules.starter_positions
        if slot in DIRECT_POSITIONS
    )
    for position, required in sorted(direct_requirements.items()):
        actual = positions.get(position, 0)
        if actual < required:
            issues.append(
                RosterHealthIssue(
                    severity=CRITICAL,
                    code="MISSING_DIRECT_STARTER_DEPTH",
                    position=position,
                    message=(
                        f"{position}: roster has {actual}, but the league requires "
                        f"{required} direct starter slot"
                        f"{'s' if required != 1 else ''}."
                    ),
                )
            )

    flex_slots = sum(
        1 for slot in league.rules.starter_positions if slot in FLEX_SLOTS
    )
    direct_flex_demand = sum(
        direct_requirements.get(position, 0)
        for position in FLEX_ELIGIBLE
    )
    flex_eligible_count = sum(
        positions.get(position, 0)
        for position in FLEX_ELIGIBLE
    )
    minimum_flex_eligible = direct_flex_demand + flex_slots
    if minimum_flex_eligible and flex_eligible_count < minimum_flex_eligible:
        issues.append(
            RosterHealthIssue(
                severity=CRITICAL,
                code="NOT_ENOUGH_FLEX_ELIGIBLE_PLAYERS",
                message=(
                    "Not enough RB/WR/TE players are rostered to fill all direct "
                    "RB/WR/TE and FLEX starter requirements."
                ),
            )
        )
    elif minimum_flex_eligible and flex_eligible_count == minimum_flex_eligible:
        issues.append(
            RosterHealthIssue(
                severity=WARNING,
                code="NO_FLEX_BENCH_DEPTH",
                message=(
                    "RB/WR/TE depth exactly matches the minimum starter demand; "
                    "there is no flex-eligible bench cushion."
                ),
            )
        )

    if open_starters:
        issues.append(
            RosterHealthIssue(
                severity=WARNING,
                code="OPEN_STARTER_SLOTS",
                message=(
                    f"{open_starters} starter slot"
                    f"{'s are' if open_starters != 1 else ' is'} currently unfilled "
                    "in Sleeper."
                ),
            )
        )

    for player_id in player_ids:
        player = player_catalog.get(player_id) or {}
        name = _player_name(player, player_id)
        raw_status = (
            str(player.get("injury_status") or "").strip()
            or str(player.get("status") or "").strip()
        )
        status = raw_status.casefold()
        if status in SERIOUS_STATUSES:
            issues.append(
                RosterHealthIssue(
                    severity=CRITICAL,
                    code="PLAYER_UNAVAILABLE",
                    player_id=player_id,
                    player_name=name,
                    position=str(player.get("position") or "").strip().upper() or None,
                    message=f"{name}: {raw_status or 'Unavailable'}",
                )
            )
        elif status in QUESTIONABLE_STATUSES:
            issues.append(
                RosterHealthIssue(
                    severity=WARNING,
                    code="PLAYER_QUESTIONABLE",
                    player_id=player_id,
                    player_name=name,
                    position=str(player.get("position") or "").strip().upper() or None,
                    message=f"{name}: Questionable",
                )
            )

    if any(row.severity == CRITICAL for row in issues):
        status = NEEDS_ATTENTION
    elif any(row.severity == WARNING for row in issues):
        status = WATCH
    else:
        status = READY

    return RosterHealthSummary(
        status=status,
        roster_size=len(player_ids),
        starter_slots=starter_slots,
        filled_starter_slots=filled_starters,
        open_starter_slots=open_starters,
        position_counts=dict(sorted(positions.items())),
        issues=tuple(issues),
    )


def _my_roster(league: FantasyLeagueState) -> Roster | None:
    if league.my_platform_roster_id:
        for roster in league.rosters:
            if roster.platform_roster_id == league.my_platform_roster_id:
                return roster

    if league.current_platform_user_id:
        for roster in league.rosters:
            if roster.platform_user_id == league.current_platform_user_id:
                return roster

    return None


def _player_name(player: Mapping[str, Any], player_id: str) -> str:
    full_name = str(player.get("full_name") or "").strip()
    if full_name:
        return full_name
    first = str(player.get("first_name") or "").strip()
    last = str(player.get("last_name") or "").strip()
    return f"{first} {last}".strip() or player_id
