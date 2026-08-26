from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import httpx

from .models import DraftState, FantasyLeagueState, LeagueRules, Manager, Roster

API_BASE = "https://api.sleeper.app/v1/"

_RULE_SETTING_KEYS = (
    "best_ball",
    "daily_waivers",
    "daily_waivers_days",
    "offseason_adds",
    "pick_trading",
    "playoff_seed_type",
    "playoff_type",
    "reserve_allow_cov",
    "reserve_allow_doubtful",
    "reserve_allow_na",
    "reserve_allow_out",
    "reserve_allow_sus",
    "reserve_allow_unknown",
    "reserve_allow_dnr",
    "trade_review_days",
    "trade_veto",
    "waiver_clear_days",
    "waiver_day_of_week",
    "waiver_type",
)

_POSITION_LIMIT_KEYS = {
    "QB": "max_qb",
    "RB": "max_rb",
    "WR": "max_wr",
    "TE": "max_te",
    "K": "max_k",
    "DEF": "max_def",
}

_DRAFT_SLOT_KEYS = {
    "QB": "slots_qb",
    "RB": "slots_rb",
    "WR": "slots_wr",
    "TE": "slots_te",
    "FLEX": "slots_flex",
    "SUPER_FLEX": "slots_super_flex",
    "K": "slots_k",
    "DEF": "slots_def",
    "BN": "slots_bn",
}


@dataclass(frozen=True)
class SleeperLeagueBundle:
    league: Mapping[str, Any]
    users: Sequence[Mapping[str, Any]]
    rosters: Sequence[Mapping[str, Any]]
    drafts: Sequence[Mapping[str, Any]]


class SleeperClient:
    """Small read-only adapter around Sleeper's public NFL fantasy API."""

    def __init__(
        self,
        *,
        base_url: str = API_BASE,
        timeout_seconds: float = 20.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._owns_client = client is None
        normalized_base = base_url.rstrip("/") + "/"
        self._client = client or httpx.Client(
            base_url=normalized_base,
            timeout=timeout_seconds,
            headers={"Accept": "application/json", "User-Agent": "PropWar-FantasyHQ/1.0"},
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "SleeperClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _get_json(self, path: str) -> Any:
        response = self._client.get(path.lstrip("/"))
        response.raise_for_status()
        return response.json()

    def fetch_league_bundle(self, league_id: str) -> SleeperLeagueBundle:
        league_id = str(league_id).strip()
        if not league_id:
            raise ValueError("league_id is required")
        league = self._get_json(f"league/{league_id}")
        if not isinstance(league, dict) or str(league.get("league_id") or "") != league_id:
            raise ValueError("Sleeper returned an unexpected league object")
        users = self._get_json(f"league/{league_id}/users") or []
        rosters = self._get_json(f"league/{league_id}/rosters") or []
        drafts = self._get_json(f"league/{league_id}/drafts") or []
        if not isinstance(users, list) or not isinstance(rosters, list) or not isinstance(drafts, list):
            raise ValueError("Sleeper returned malformed league resources")
        return SleeperLeagueBundle(league=league, users=users, rosters=rosters, drafts=drafts)

    def fetch_normalized_league(
        self,
        league_id: str,
        *,
        current_user_id: str | None = None,
    ) -> FantasyLeagueState:
        return normalize_sleeper_bundle(
            self.fetch_league_bundle(league_id),
            current_user_id=current_user_id,
        )


def _as_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_rules(league: Mapping[str, Any]) -> LeagueRules:
    settings = dict(league.get("settings") or {})
    scoring = dict(league.get("scoring_settings") or {})
    roster_positions = tuple(str(slot) for slot in (league.get("roster_positions") or []))
    position_limits = {
        position: int(settings[key])
        for position, key in _POSITION_LIMIT_KEYS.items()
        if _as_int(settings.get(key)) is not None and int(settings[key]) > 0
    }
    rule_settings = {key: settings[key] for key in _RULE_SETTING_KEYS if key in settings}
    return LeagueRules(
        roster_positions=roster_positions,
        scoring_settings=scoring,
        waiver_budget=_as_int(settings.get("waiver_budget")),
        max_keepers=_as_int(settings.get("max_keepers")),
        playoff_teams=_as_int(settings.get("playoff_teams")),
        playoff_week_start=_as_int(settings.get("playoff_week_start")),
        trade_deadline=_as_int(settings.get("trade_deadline")),
        reserve_slots=_as_int(settings.get("reserve_slots")) or 0,
        taxi_slots=_as_int(settings.get("taxi_slots")) or 0,
        position_limits=position_limits,
        rule_settings=rule_settings,
        raw_settings=settings,
    )


def _normalize_draft(drafts: Sequence[Mapping[str, Any]]) -> DraftState | None:
    if not drafts:
        return None
    draft = dict(drafts[0])
    settings = dict(draft.get("settings") or {})
    slot_counts = {
        slot: int(settings[key])
        for slot, key in _DRAFT_SLOT_KEYS.items()
        if _as_int(settings.get(key)) is not None and int(settings[key]) > 0
    }
    raw_order = draft.get("draft_order") or {}
    draft_order = (
        {
            str(user_id): int(slot)
            for user_id, slot in raw_order.items()
            if _as_int(slot) is not None
        }
        if isinstance(raw_order, dict)
        else {}
    )
    return DraftState(
        platform_draft_id=str(draft.get("draft_id") or ""),
        status=str(draft.get("status") or "unknown"),
        draft_type=str(draft.get("type")) if draft.get("type") is not None else None,
        rounds=_as_int(settings.get("rounds")),
        teams=_as_int(settings.get("teams")),
        start_time_ms=_as_int(draft.get("start_time")),
        draft_order=draft_order,
        slot_counts=slot_counts,
        raw=draft,
    )


def _normalize_managers(users: Sequence[Mapping[str, Any]]) -> tuple[Manager, ...]:
    rows: list[Manager] = []
    for user in users:
        user_id = str(user.get("user_id") or "").strip()
        if not user_id:
            continue
        metadata = dict(user.get("metadata") or {})
        rows.append(
            Manager(
                platform_user_id=user_id,
                display_name=str(user.get("display_name") or ""),
                team_name=str(metadata.get("team_name")) if metadata.get("team_name") else None,
                is_owner=bool(user.get("is_owner")),
            )
        )
    return tuple(rows)


def _normalize_rosters(rosters: Sequence[Mapping[str, Any]]) -> tuple[Roster, ...]:
    rows: list[Roster] = []
    for roster in rosters:
        roster_id = str(roster.get("roster_id") or "").strip()
        if not roster_id:
            continue
        owner_id = str(roster.get("owner_id") or "").strip() or None
        rows.append(
            Roster(
                platform_roster_id=roster_id,
                platform_user_id=owner_id,
                players=tuple(str(value) for value in (roster.get("players") or []) if value not in (None, "")),
                starters=tuple(str(value) for value in (roster.get("starters") or []) if value not in (None, "")),
                reserve=tuple(str(value) for value in (roster.get("reserve") or []) if value not in (None, "")),
                taxi=tuple(str(value) for value in (roster.get("taxi") or []) if value not in (None, "")),
                settings=dict(roster.get("settings") or {}),
            )
        )
    return tuple(rows)


def normalize_sleeper_bundle(
    bundle: SleeperLeagueBundle,
    *,
    current_user_id: str | None = None,
) -> FantasyLeagueState:
    league = dict(bundle.league)
    rules = _normalize_rules(league)
    draft = _normalize_draft(bundle.drafts)
    managers = _normalize_managers(bundle.users)
    rosters = _normalize_rosters(bundle.rosters)

    normalized_user_id = str(current_user_id).strip() if current_user_id is not None else None
    my_roster = next(
        (roster for roster in rosters if normalized_user_id and roster.platform_user_id == normalized_user_id),
        None,
    )

    rules_ready = bool(rules.roster_positions and _as_int(league.get("total_rosters")))
    draft_ready = bool(draft and draft.ready)
    ownership_ready = bool(
        draft
        and draft.status == "complete"
        and rosters
        and any(roster.has_players for roster in rosters)
    )

    return FantasyLeagueState(
        platform="SLEEPER",
        platform_league_id=str(league.get("league_id") or ""),
        name=str(league.get("name") or ""),
        season=str(league.get("season") or ""),
        status=str(league.get("status") or "unknown"),
        team_count=_as_int(league.get("total_rosters")) or len(rosters),
        previous_platform_league_id=(
            str(league.get("previous_league_id")) if league.get("previous_league_id") else None
        ),
        current_platform_user_id=normalized_user_id,
        my_platform_roster_id=my_roster.platform_roster_id if my_roster else None,
        rules=rules,
        draft=draft,
        managers=managers,
        rosters=rosters,
        rules_ready=rules_ready,
        draft_ready=draft_ready,
        ownership_ready=ownership_ready,
    )
