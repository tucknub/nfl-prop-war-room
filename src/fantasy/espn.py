from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping
from urllib.parse import quote

import httpx
from cryptography.fernet import Fernet, InvalidToken


ESPN_READ_BASE = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl"
ESPN_FAN_BASE = "https://fan.api.espn.com/apis/v2/fans"
DEFAULT_TIMEOUT_SECONDS = 12.0
DEFAULT_VIEWS = ("mSettings", "mTeam", "mRoster", "mStatus", "mMatchupScore")

DEFAULT_POSITION_MAP = {
    1: "QB",
    2: "RB",
    3: "WR",
    4: "TE",
    5: "K",
    16: "DST",
}
LINEUP_POSITION_MAP = {
    0: "QB",
    2: "RB",
    4: "WR",
    6: "TE",
    16: "DST",
    17: "K",
}
LINEUP_SLOT_MAP = {
    0: "QB",
    2: "RB",
    4: "WR",
    6: "TE",
    16: "D/ST",
    17: "K",
    20: "Bench",
    21: "IR",
    23: "FLEX",
}
PRO_TEAM_MAP = {
    0: "FA",
    1: "ATL",
    2: "BUF",
    3: "CHI",
    4: "CIN",
    5: "CLE",
    6: "DAL",
    7: "DEN",
    8: "DET",
    9: "GB",
    10: "TEN",
    11: "IND",
    12: "KC",
    13: "LV",
    14: "LAR",
    15: "MIA",
    16: "MIN",
    17: "NE",
    18: "NO",
    19: "NYG",
    20: "NYJ",
    21: "PHI",
    22: "ARI",
    23: "PIT",
    24: "LAC",
    25: "SF",
    26: "SEA",
    27: "TB",
    28: "WSH",
    29: "CAR",
    30: "JAX",
    33: "BAL",
    34: "HOU",
}

_LEAGUE_URL_PATTERNS = (
    re.compile(r"[?&]leagueId=(\d+)", re.IGNORECASE),
    re.compile(r"/leagues/(\d+)", re.IGNORECASE),
)
_SWID_RE = re.compile(
    r"^\{?[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}?$"
)


class EspnFantasyError(RuntimeError):
    pass


class EspnAuthenticationError(EspnFantasyError):
    pass


class EspnSchemaError(EspnFantasyError):
    pass


@dataclass(frozen=True)
class EspnCredentials:
    espn_s2: str
    swid: str

    def normalized(self) -> "EspnCredentials":
        espn_s2 = str(self.espn_s2 or "").strip()
        swid = str(self.swid or "").strip()
        if not espn_s2:
            raise ValueError("espn_s2 is required for a private ESPN league.")
        if len(espn_s2) < 20:
            raise ValueError("espn_s2 does not look like a complete ESPN session cookie.")
        if not _SWID_RE.match(swid):
            raise ValueError("SWID must be the ESPN GUID, with or without curly braces.")
        if not swid.startswith("{"):
            swid = "{" + swid.strip("{}") + "}"
        return EspnCredentials(espn_s2=espn_s2, swid=swid.upper())


def _normalize_owner_id(value: object) -> str:
    return str(value or "").strip().strip("{}").upper()


def _team_name(team: Mapping[str, Any]) -> str:
    name = str(team.get("name") or "").strip()
    if name:
        return name
    location = str(team.get("location") or "").strip()
    nickname = str(team.get("nickname") or "").strip()
    fallback = f"{location} {nickname}".strip()
    return fallback or str(team.get("abbrev") or team.get("abbreviation") or f"Team {team.get('id', '?')}").strip()


def _position_from_player(player: Mapping[str, Any]) -> str:
    # ESPN football eligibleSlots are the most reliable position signal and
    # use the lineup-slot ID table. Prefer them over defaultPositionId, whose
    # community documentation has differed across endpoint families.
    for raw_slot in player.get("eligibleSlots") or []:
        try:
            slot = int(raw_slot)
        except (TypeError, ValueError):
            continue
        if slot in LINEUP_POSITION_MAP:
            return LINEUP_POSITION_MAP[slot]

    try:
        default_position = int(player.get("defaultPositionId"))
    except (TypeError, ValueError):
        default_position = -1
    return DEFAULT_POSITION_MAP.get(default_position, "")


def _league_ids_from_value(value: Any) -> set[str]:
    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, Mapping):
            for key, item in node.items():
                normalized_key = str(key or "").replace("_", "").casefold()
                if normalized_key == "leagueid":
                    candidate = str(item or "").strip()
                    if candidate.isdigit():
                        found.add(candidate)
                walk(item)
            return
        if isinstance(node, (list, tuple)):
            for item in node:
                walk(item)
            return
        if isinstance(node, str):
            for pattern in _LEAGUE_URL_PATTERNS:
                found.update(pattern.findall(node))

    walk(value)
    return found


def _derive_fernet(secret: str) -> Fernet:
    raw = str(secret or "").strip()
    if len(raw) < 16:
        raise ValueError("ESPN credential encryption secret is not configured.")
    digest = hashlib.sha256(("propwar-espn-credentials-v1:" + raw).encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def seal_credentials(credentials: EspnCredentials, secret: str) -> str:
    normalized = credentials.normalized()
    payload = json.dumps(
        {"espn_s2": normalized.espn_s2, "swid": normalized.swid},
        separators=(",", ":"),
    ).encode("utf-8")
    return _derive_fernet(secret).encrypt(payload).decode("ascii")


def open_credentials(envelope: str, secret: str) -> EspnCredentials:
    try:
        raw = _derive_fernet(secret).decrypt(str(envelope or "").encode("ascii"))
        payload = json.loads(raw.decode("utf-8"))
    except (InvalidToken, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise EspnAuthenticationError("Stored ESPN credentials could not be decrypted. Reconnect ESPN.") from exc
    return EspnCredentials(
        espn_s2=str(payload.get("espn_s2") or ""),
        swid=str(payload.get("swid") or ""),
    ).normalized()


def credential_secret_from_mapping(secrets: Mapping[str, Any]) -> str:
    direct = str(secrets.get("ESPN_CREDENTIAL_SECRET", "") or "").strip()
    if direct:
        return direct
    auth = secrets.get("auth")
    if isinstance(auth, Mapping):
        return str(auth.get("cookie_secret", "") or "").strip()
    return ""


class EspnFantasyClient:
    """Read-only ESPN Fantasy Football adapter for PropWar."""

    def __init__(
        self,
        credentials: EspnCredentials | None = None,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.credentials = credentials.normalized() if credentials is not None else None
        self._test_transport_injected = transport is not None
        cookies: dict[str, str] = {}
        if self.credentials is not None:
            cookies = {
                "espn_s2": self.credentials.espn_s2,
                "SWID": self.credentials.swid,
            }
        self._client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            cookies=cookies,
            transport=transport,
            headers={
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://fantasy.espn.com/",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/152.0.0.0 Safari/537.36"
                ),
            },
        )

    def __enter__(self) -> "EspnFantasyClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _get_json(
        self,
        url: str,
        *,
        params: Iterable[tuple[str, str]] | Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        try:
            response = self._client.get(url, params=params)
        except httpx.HTTPError as exc:
            raise EspnFantasyError(f"ESPN request failed: {exc}") from exc

        if response.status_code in {401, 403}:
            raise EspnAuthenticationError(
                "ESPN rejected this browser session for Elwood TKO. "
                "Refresh espn_s2 and SWID from fantasy.espn.com while logged into the account that owns team 7."
            )
        if response.status_code == 404:
            raise EspnFantasyError("ESPN league was not found for this season.")
        if response.status_code >= 400:
            raise EspnFantasyError(f"ESPN returned HTTP {response.status_code}.")
        content_type = str(response.headers.get("content-type") or "").casefold()
        if "json" not in content_type:
            raise EspnAuthenticationError(
                "ESPN returned a sign-in/HTML response instead of fantasy data. "
                "Refresh espn_s2 and SWID from fantasy.espn.com."
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise EspnSchemaError("ESPN returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise EspnSchemaError("ESPN returned an unexpected response shape.")

        messages = [
            str(value or "").strip()
            for value in payload.get("messages") or []
        ]
        detail_types = {
            str(row.get("type") or "").strip()
            for row in payload.get("details") or []
            if isinstance(row, Mapping)
        }
        if any("not authorized" in message.casefold() for message in messages) or any(
            value.startswith("AUTH_") for value in detail_types
        ):
            raise EspnAuthenticationError(
                "ESPN says this browser session is not authorized for Elwood TKO. "
                "Refresh espn_s2 and SWID from fantasy.espn.com while logged into the account that owns team 7."
            )

        return payload

    def _fetch_league_with_espn_api(
        self,
        league_id: str | int,
        *,
        season: int,
    ) -> dict[str, Any]:
        if self.credentials is None:
            raise EspnAuthenticationError(
                "Private ESPN league sync requires espn_s2 and SWID."
            )

        try:
            from espn_api.requests.espn_requests import (
                ESPNAccessDenied,
                ESPNInvalidLeague,
                ESPNUnknownError,
                EspnFantasyRequests,
            )
        except ImportError as exc:
            raise EspnFantasyError(
                "The maintained espn-api client is unavailable in this deployment."
            ) from exc

        request = EspnFantasyRequests(
            sport="nfl",
            year=int(season),
            league_id=int(league_id),
            cookies={
                "espn_s2": self.credentials.espn_s2,
                "SWID": self.credentials.swid,
            },
        )
        try:
            payload = request.get_league()
        except ESPNAccessDenied as exc:
            raise EspnAuthenticationError(
                "ESPN rejected these private-league credentials."
            ) from exc
        except ESPNInvalidLeague as exc:
            raise EspnFantasyError(
                f"ESPN says league {league_id} does not exist for {int(season)}."
            ) from exc
        except ESPNUnknownError as exc:
            raise EspnFantasyError(f"ESPN request failed: {exc}") from exc
        except Exception as exc:
            raise EspnFantasyError(
                f"The maintained ESPN client failed: {type(exc).__name__}: {exc}"
            ) from exc

        if not isinstance(payload, dict):
            raise EspnSchemaError(
                "The maintained ESPN client returned an unexpected response shape."
            )
        return payload

    def fetch_league(
        self,
        league_id: str | int,
        *,
        season: int = 2026,
        views: Iterable[str] = DEFAULT_VIEWS,
        extra_params: Mapping[str, str | int] | None = None,
    ) -> dict[str, Any]:
        league = str(league_id or "").strip()
        if not league.isdigit():
            raise ValueError("ESPN league ID must be numeric.")
        year = int(season)
        url = f"{ESPN_READ_BASE}/seasons/{year}/segments/0/leagues/{league}"
        params: list[tuple[str, str]] = [("view", str(view)) for view in views]
        if extra_params:
            params.extend((str(key), str(value)) for key, value in extra_params.items())
        payload = self._get_json(url, params=params)
        returned_id = str(payload.get("id") or "").strip()
        returned_season = int(payload.get("seasonId") or 0)
        if returned_id and returned_id != league:
            raise EspnSchemaError("ESPN returned a different league ID than requested.")
        if returned_season and returned_season != year:
            raise EspnSchemaError("ESPN returned a different season than requested.")
        return payload

    def _discover_named_league_with_requests(
        self,
        *,
        season: int,
        league_name: str,
    ) -> dict[str, Any] | None:
        if self.credentials is None:
            return None

        try:
            import requests
        except ImportError:
            return None

        target_name = str(league_name or "").strip().casefold()
        if not target_name:
            return None

        cookies = {
            "espn_s2": self.credentials.espn_s2,
            "SWID": self.credentials.swid,
        }
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://fantasy.espn.com/",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/152.0.0.0 Safari/537.36"
            ),
        }

        profile: Any | None = None
        swid_variants = [
            self.credentials.swid.strip("{}"),
            self.credentials.swid,
        ]
        for swid_value in dict.fromkeys(swid_variants):
            try:
                response = requests.get(
                    f"{ESPN_FAN_BASE}/{quote(swid_value, safe='')}",
                    params={
                        "displayHiddenPrefs": "true",
                        "context": "fantasy",
                        "useCookieAuth": "true",
                        "source": "fantasyapp-web",
                    },
                    headers=headers,
                    cookies=cookies,
                    timeout=DEFAULT_TIMEOUT_SECONDS,
                )
            except requests.RequestException:
                continue
            if response.status_code != 200:
                continue
            try:
                candidate_profile = response.json()
            except ValueError:
                continue
            if isinstance(candidate_profile, (dict, list)):
                profile = candidate_profile
                break

        if profile is None:
            return None

        candidate_ids = sorted(
            _league_ids_from_value(profile),
            key=lambda value: int(value),
        )
        for candidate_id in candidate_ids[:32]:
            try:
                payload = self._fetch_league_with_espn_api(
                    candidate_id,
                    season=season,
                )
            except EspnFantasyError:
                continue

            settings = (
                payload.get("settings")
                if isinstance(payload.get("settings"), Mapping)
                else {}
            )
            candidate_name = str(
                settings.get("name")
                or payload.get("name")
                or ""
            ).strip()
            candidate_season = int(payload.get("seasonId") or season)
            if (
                candidate_season == int(season)
                and candidate_name.casefold() == target_name
            ):
                snapshot = normalize_league_snapshot(
                    payload,
                    swid=self.credentials.swid,
                    team_id=None,
                )
                snapshot["discovered_relink"] = True
                return snapshot

        return None

    def fetch_knockout_snapshot(
        self,
        league_id: str | int,
        *,
        season: int,
        team_id: int,
        swid: str | None = None,
        league_name: str | None = None,
    ) -> dict[str, Any]:
        primary_error: str | None = None

        # Production path: use the maintained espn-api package, which mirrors
        # ESPN Fantasy's long-running requests + cookie behavior.
        if not self._test_transport_injected:
            try:
                payload = self._fetch_league_with_espn_api(
                    league_id,
                    season=season,
                )
                return normalize_league_snapshot(
                    payload,
                    swid=swid,
                    team_id=int(team_id),
                )
            except EspnFantasyError as exc:
                primary_error = str(exc)

        # Fallback/test path: direct read calls kept independently so one
        # implementation can still work if the other breaks.
        try:
            base = self.fetch_league(
                league_id,
                season=season,
                views=("mSettings", "mTeam", "mStatus"),
            )
            status = base.get("status") if isinstance(base.get("status"), Mapping) else {}
            scoring_period = int(
                status.get("currentScoringPeriod")
                or status.get("currentMatchupPeriod")
                or base.get("scoringPeriodId")
                or 1
            )
            scoring_period = max(1, scoring_period)

            roster_payload = self.fetch_league(
                league_id,
                season=season,
                views=("mRoster",),
                extra_params={
                    "scoringPeriodId": scoring_period,
                    "rosterForTeamId": int(team_id),
                },
            )
            score_payload = self.fetch_league(
                league_id,
                season=season,
                views=("mMatchupScore",),
                extra_params={"scoringPeriodId": scoring_period},
            )

            merged = dict(base)
            base_teams = [
                dict(row)
                for row in base.get("teams") or []
                if isinstance(row, Mapping)
            ]
            roster_teams = {
                int(row.get("id") or 0): dict(row)
                for row in roster_payload.get("teams") or []
                if isinstance(row, Mapping)
            }
            merged_teams: list[dict[str, Any]] = []
            seen_ids: set[int] = set()
            for team in base_teams:
                current_id = int(team.get("id") or 0)
                if current_id in roster_teams:
                    roster_team = roster_teams[current_id]
                    if isinstance(roster_team.get("roster"), Mapping):
                        team["roster"] = dict(roster_team["roster"])
                    if isinstance(roster_team.get("transactionCounter"), Mapping):
                        team["transactionCounter"] = dict(roster_team["transactionCounter"])
                merged_teams.append(team)
                seen_ids.add(current_id)
            for current_id, team in roster_teams.items():
                if current_id not in seen_ids:
                    merged_teams.append(team)
            merged["teams"] = merged_teams
            merged["schedule"] = list(score_payload.get("schedule") or [])
            merged["scoringPeriodId"] = scoring_period

            return normalize_league_snapshot(
                merged,
                swid=swid,
                team_id=int(team_id),
            )
        except EspnFantasyError as fallback_exc:
            if not self._test_transport_injected and league_name:
                discovered = self._discover_named_league_with_requests(
                    season=season,
                    league_name=league_name,
                )
                if discovered is not None:
                    return discovered

            if primary_error:
                raise EspnFantasyError(
                    "Both ESPN sync paths failed. "
                    f"Maintained client: {primary_error} "
                    f"Direct fallback: {fallback_exc}"
                ) from fallback_exc
            raise


    def discover_leagues(self, *, season: int = 2026) -> list[dict[str, Any]]:
        if self.credentials is None:
            raise EspnAuthenticationError("Private ESPN league discovery requires espn_s2 and SWID.")

        swid_path = quote(self.credentials.swid.strip("{}"), safe="")
        profile = self._get_json(
            f"{ESPN_FAN_BASE}/{swid_path}",
            params={
                "displayHiddenPrefs": "true",
                "context": "fantasy",
                "useCookieAuth": "true",
                "source": "fantasyapp-web",
            },
        )
        candidate_ids = sorted(_league_ids_from_value(profile), key=lambda value: int(value))
        leagues: list[dict[str, Any]] = []
        for league_id in candidate_ids[:32]:
            try:
                payload = self.fetch_league(
                    league_id,
                    season=season,
                    views=("mSettings", "mTeam", "mStatus"),
                )
                snapshot = normalize_league_snapshot(payload, swid=self.credentials.swid)
            except EspnFantasyError:
                continue
            leagues.append(
                {
                    "league_id": snapshot["league_id"],
                    "league_name": snapshot["league_name"],
                    "team_id": snapshot["team_id"],
                    "team_name": snapshot["team_name"],
                    "team_count": snapshot["team_count"],
                    "season": snapshot["season"],
                }
            )
        return leagues


def normalize_league_snapshot(
    payload: Mapping[str, Any],
    *,
    swid: str | None = None,
    team_id: int | None = None,
) -> dict[str, Any]:
    league_id = str(payload.get("id") or "").strip()
    season = int(payload.get("seasonId") or 0)
    settings = payload.get("settings") if isinstance(payload.get("settings"), Mapping) else {}
    status = payload.get("status") if isinstance(payload.get("status"), Mapping) else {}
    teams = [dict(row) for row in payload.get("teams") or [] if isinstance(row, Mapping)]

    if not league_id or not season:
        raise EspnSchemaError("ESPN league response is missing league identity.")

    league_name = str(settings.get("name") or payload.get("name") or f"ESPN League {league_id}").strip()
    team_count = int(settings.get("size") or len(teams) or 0)

    owner_id = _normalize_owner_id(swid)
    my_team: dict[str, Any] | None = None
    target_team_id = int(team_id or 0)
    if target_team_id > 0:
        my_team = next(
            (
                team
                for team in teams
                if int(team.get("id") or 0) == target_team_id
            ),
            None,
        )

    if my_team is None and owner_id:
        for team in teams:
            owners = [_normalize_owner_id(value) for value in team.get("owners") or []]
            owners.extend(
                _normalize_owner_id(team.get(key))
                for key in ("primaryOwner", "ownerId")
                if team.get(key)
            )
            if owner_id in owners:
                my_team = team
                break

    if my_team is None and len(teams) == 1:
        my_team = teams[0]
    if my_team is None:
        raise EspnSchemaError(
            "PropWar could read the ESPN league but could not identify the configured fantasy team."
        )

    roster_rows: list[dict[str, Any]] = []
    roster = my_team.get("roster") if isinstance(my_team.get("roster"), Mapping) else {}
    for entry in roster.get("entries") or []:
        if not isinstance(entry, Mapping):
            continue
        pool = entry.get("playerPoolEntry") if isinstance(entry.get("playerPoolEntry"), Mapping) else {}
        player = pool.get("player") if isinstance(pool.get("player"), Mapping) else {}
        name = str(player.get("fullName") or "").strip()
        position = _position_from_player(player)
        try:
            pro_team_id = int(player.get("proTeamId"))
        except (TypeError, ValueError):
            pro_team_id = 0
        nfl_team = PRO_TEAM_MAP.get(pro_team_id, "")
        if not name or not position or not nfl_team:
            continue
        try:
            lineup_slot_id = int(entry.get("lineupSlotId"))
        except (TypeError, ValueError):
            lineup_slot_id = -1
        roster_rows.append(
            {
                "player": name,
                "position": position,
                "nfl_team": nfl_team,
                "espn_player_id": str(entry.get("playerId") or player.get("id") or ""),
                "lineup_slot_id": lineup_slot_id,
                "lineup_role": LINEUP_SLOT_MAP.get(lineup_slot_id, str(lineup_slot_id)),
                "injury_status": str(player.get("injuryStatus") or entry.get("injuryStatus") or "ACTIVE"),
            }
        )

    acquisition = settings.get("acquisitionSettings") if isinstance(settings.get("acquisitionSettings"), Mapping) else {}
    try:
        faab_start = int(acquisition.get("acquisitionBudget"))
    except (TypeError, ValueError):
        faab_start = 0
    tx = my_team.get("transactionCounter") if isinstance(my_team.get("transactionCounter"), Mapping) else {}
    try:
        faab_spent = int(tx.get("acquisitionBudgetSpent") or 0)
    except (TypeError, ValueError):
        faab_spent = 0
    faab_remaining = max(0, faab_start - faab_spent) if faab_start > 0 else None

    draft_settings = settings.get("draftSettings") if isinstance(settings.get("draftSettings"), Mapping) else {}
    try:
        roster_size = int(draft_settings.get("slotCount") or 0)
    except (TypeError, ValueError):
        roster_size = 0
    if roster_size <= 0:
        roster_settings = settings.get("rosterSettings") if isinstance(settings.get("rosterSettings"), Mapping) else {}
        lineup_counts = roster_settings.get("lineupSlotCounts") if isinstance(roster_settings.get("lineupSlotCounts"), Mapping) else {}
        roster_size = sum(
            int(value or 0)
            for key, value in lineup_counts.items()
            if str(key) != "21"
        )

    current_week = int(
        status.get("currentScoringPeriod")
        or status.get("currentMatchupPeriod")
        or payload.get("scoringPeriodId")
        or 0
    )

    current_score: float | None = None
    team_id = int(my_team.get("id") or 0)
    for matchup in payload.get("schedule") or []:
        if not isinstance(matchup, Mapping):
            continue
        matchup_week = int(matchup.get("matchupPeriodId") or 0)
        if current_week and matchup_week and matchup_week != current_week:
            continue
        for side_name in ("home", "away"):
            side = matchup.get(side_name)
            if not isinstance(side, Mapping) or int(side.get("teamId") or 0) != team_id:
                continue
            raw_score = side.get("totalPoints")
            if raw_score is not None:
                try:
                    current_score = float(raw_score)
                except (TypeError, ValueError):
                    current_score = None
            break
        if current_score is not None:
            break

    return {
        "provider": "ESPN",
        "league_id": league_id,
        "league_name": league_name,
        "season": season,
        "team_count": team_count,
        "team_id": team_id,
        "team_name": _team_name(my_team),
        "current_week": current_week,
        "faab_start": faab_start or None,
        "faab_spent": faab_spent,
        "faab_remaining": faab_remaining,
        "roster_size": roster_size or len(roster_rows),
        "roster": roster_rows,
        "current_score": current_score,
        "is_public": bool(settings.get("isPublic", False)),
    }
