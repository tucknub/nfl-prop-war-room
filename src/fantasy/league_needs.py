from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Mapping

from .models import FantasyLeagueState
from .roster_health import DIRECT_POSITIONS, FLEX_ELIGIBLE, FLEX_SLOTS
from .team_explorer import HIGH, MEDIUM, LeagueTeamProfile, build_league_team_profile


TWO_WAY = "TWO_WAY"
ONE_WAY = "ONE_WAY"


@dataclass(frozen=True)
class LeagueNeedsRow:
    roster_id: str
    team_name: str
    high_needs: tuple[str, ...]
    medium_needs: tuple[str, ...]
    depth_positions: tuple[str, ...]
    roster_size: int
    serious_status_count: int
    questionable_status_count: int
    is_mine: bool = False


@dataclass(frozen=True)
class TradeFitSignal:
    roster_id: str
    team_name: str
    signal: str
    they_can_help_me_at: tuple[str, ...]
    i_can_help_them_at: tuple[str, ...]
    their_needs: tuple[str, ...]
    my_needs: tuple[str, ...]

    @property
    def two_way(self) -> bool:
        return self.signal == TWO_WAY


@dataclass(frozen=True)
class LeagueNeedsBoard:
    rows: tuple[LeagueNeedsRow, ...]
    trade_fits: tuple[TradeFitSignal, ...]

    @property
    def team_count(self) -> int:
        return len(self.rows)

    @property
    def high_need_team_count(self) -> int:
        return sum(1 for row in self.rows if row.high_needs)

    @property
    def two_way_trade_fit_count(self) -> int:
        return sum(1 for row in self.trade_fits if row.two_way)


def build_league_needs_board(
    league: FantasyLeagueState,
    player_catalog: Mapping[str, Mapping[str, Any]],
) -> LeagueNeedsBoard:
    profiles: list[LeagueTeamProfile] = []
    for roster in league.rosters:
        profiles.append(
            build_league_team_profile(
                league,
                roster.platform_roster_id,
                player_catalog,
                trends=(),
            )
        )

    profile_by_roster = {profile.roster_id: profile for profile in profiles}
    rows = tuple(
        sorted(
            (
                LeagueNeedsRow(
                    roster_id=profile.roster_id,
                    team_name=profile.team_name,
                    high_needs=_need_labels(profile, HIGH),
                    medium_needs=_need_labels(profile, MEDIUM),
                    depth_positions=_depth_positions(league, profile),
                    roster_size=profile.roster_size,
                    serious_status_count=profile.serious_status_count,
                    questionable_status_count=profile.questionable_status_count,
                    is_mine=profile.roster_id == league.my_platform_roster_id,
                )
                for profile in profiles
            ),
            key=lambda row: (
                0 if row.is_mine else 1,
                -len(row.high_needs),
                row.team_name.casefold(),
                row.roster_id,
            ),
        )
    )

    my_profile = (
        profile_by_roster.get(league.my_platform_roster_id or "")
        if league.my_platform_roster_id
        else None
    )
    if my_profile is None:
        return LeagueNeedsBoard(rows=rows, trade_fits=())

    my_needs = _need_position_set(my_profile)
    my_depth = set(_depth_positions(league, my_profile))

    trade_fits: list[TradeFitSignal] = []
    for profile in profiles:
        if profile.roster_id == my_profile.roster_id:
            continue

        their_needs = _need_position_set(profile)
        their_depth = set(_depth_positions(league, profile))
        they_can_help = tuple(sorted(my_needs.intersection(their_depth)))
        i_can_help = tuple(sorted(their_needs.intersection(my_depth)))

        if not they_can_help and not i_can_help:
            continue

        trade_fits.append(
            TradeFitSignal(
                roster_id=profile.roster_id,
                team_name=profile.team_name,
                signal=(TWO_WAY if they_can_help and i_can_help else ONE_WAY),
                they_can_help_me_at=they_can_help,
                i_can_help_them_at=i_can_help,
                their_needs=tuple(sorted(their_needs)),
                my_needs=tuple(sorted(my_needs)),
            )
        )

    trade_fits.sort(
        key=lambda row: (
            0 if row.signal == TWO_WAY else 1,
            -len(row.they_can_help_me_at),
            -len(row.i_can_help_them_at),
            row.team_name.casefold(),
            row.roster_id,
        )
    )
    return LeagueNeedsBoard(
        rows=rows,
        trade_fits=tuple(trade_fits),
    )


def _need_labels(profile: LeagueTeamProfile, level: str) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            need.position
            for need in profile.needs
            if need.level == level
        )
    )


def _need_position_set(profile: LeagueTeamProfile) -> set[str]:
    positions: set[str] = set()
    for need in profile.needs:
        # A healthy roster carrying exactly one QB/TE/etc. for one direct
        # starter slot is a depth watch, not enough by itself to create a
        # trade-target signal. Keep it visible on the Needs Board without
        # polluting trade-fit matching.
        if need.level == MEDIUM and "no bench cushion" in need.reason:
            continue
        if need.position == "RB/WR/TE":
            positions.update(FLEX_ELIGIBLE)
        elif need.position == "ANY":
            continue
        else:
            positions.add(need.position)
    return positions


def _depth_positions(
    league: FantasyLeagueState,
    profile: LeagueTeamProfile,
) -> tuple[str, ...]:
    direct_requirements = Counter(
        slot
        for slot in league.rules.starter_positions
        if slot in DIRECT_POSITIONS
    )
    flex_slots = sum(
        1
        for slot in league.rules.starter_positions
        if slot in FLEX_SLOTS
    )

    rows: list[str] = []
    for position, count in profile.position_counts.items():
        if position not in DIRECT_POSITIONS:
            continue

        direct = direct_requirements.get(position, 0)
        conservative_extra = count - direct
        if position in FLEX_ELIGIBLE:
            conservative_extra -= flex_slots

        if conservative_extra > 0:
            rows.append(position)

    return tuple(sorted(rows))
