from __future__ import annotations

from dataclasses import dataclass
import base64
from hashlib import sha256
import hmac
import json
import secrets
import time
from typing import Any, Iterable, Mapping
from urllib.parse import urlencode, urlsplit

import httpx


YAHOO_AUTH_URL = "https://api.login.yahoo.com/oauth2/request_auth"
YAHOO_TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
YAHOO_FANTASY_BASE = "https://fantasysports.yahooapis.com/fantasy/v2/"
DEFAULT_YAHOO_REDIRECT_URI = "https://propwar.streamlit.app/fantasy-hq"


class YahooFantasyError(RuntimeError):
    """Yahoo OAuth or Fantasy API response was unsafe or malformed."""


@dataclass(frozen=True)
class YahooOAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str = DEFAULT_YAHOO_REDIRECT_URI

    def __post_init__(self) -> None:
        object.__setattr__(self, "client_id", _canonical_text(self.client_id, "client_id"))
        object.__setattr__(
            self,
            "client_secret",
            _canonical_text(self.client_secret, "client_secret"),
        )
        object.__setattr__(
            self,
            "redirect_uri",
            _validated_https_origin_path(self.redirect_uri),
        )

    def authorization_url(self, *, state: str) -> str:
        state = _canonical_text(state, "state")
        return YAHOO_AUTH_URL + "?" + urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "state": state,
            }
        )


@dataclass(frozen=True)
class YahooOAuthToken:
    access_token: str
    refresh_token: str | None
    expires_in: int
    token_type: str = "bearer"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "access_token",
            _canonical_text(self.access_token, "access_token"),
        )
        if self.refresh_token is not None:
            object.__setattr__(
                self,
                "refresh_token",
                _canonical_text(self.refresh_token, "refresh_token"),
            )
        if isinstance(self.expires_in, bool) or not isinstance(self.expires_in, int):
            raise YahooFantasyError("Yahoo expires_in must be an integer")
        if self.expires_in <= 0:
            raise YahooFantasyError("Yahoo expires_in must be positive")
        token_type = _canonical_text(self.token_type, "token_type").casefold()
        if token_type != "bearer":
            raise YahooFantasyError("Yahoo token_type must be bearer")
        object.__setattr__(self, "token_type", token_type)


@dataclass(frozen=True)
class YahooTeamSummary:
    team_key: str
    league_key: str
    name: str
    team_id: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class YahooPlayerSummary:
    player_key: str
    name: str
    display_position: str | None
    nfl_team: str | None
    selected_position: str | None
    status: str | None


@dataclass(frozen=True)
class YahooLeagueSummary:
    league_key: str
    name: str
    season: str | None
    num_teams: int | None
    current_week: int | None
    scoring_type: str | None
    draft_status: str | None


def build_yahoo_oauth_state(
    signing_secret: str,
    *,
    now_seconds: int | None = None,
) -> str:
    secret = _canonical_text(signing_secret, "signing_secret").encode("utf-8")
    issued_at = int(time.time() if now_seconds is None else now_seconds)
    if issued_at < 0:
        raise ValueError("now_seconds must be non-negative")
    payload = {
        "iat": issued_at,
        "nonce": secrets.token_urlsafe(18),
        "purpose": "fantasy-hq-yahoo",
    }
    encoded = _b64url(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    signature = _b64url(hmac.new(secret, encoded.encode("ascii"), sha256).digest())
    return f"{encoded}.{signature}"


def validate_yahoo_oauth_state(
    state: str,
    signing_secret: str,
    *,
    now_seconds: int | None = None,
    max_age_seconds: int = 15 * 60,
) -> Mapping[str, Any]:
    state = _canonical_text(state, "state")
    secret = _canonical_text(signing_secret, "signing_secret").encode("utf-8")
    if max_age_seconds <= 0:
        raise ValueError("max_age_seconds must be positive")
    try:
        encoded, supplied_signature = state.split(".", 1)
    except ValueError as exc:
        raise YahooFantasyError("Yahoo OAuth state is malformed") from exc

    expected_signature = _b64url(
        hmac.new(secret, encoded.encode("ascii"), sha256).digest()
    )
    if not hmac.compare_digest(supplied_signature, expected_signature):
        raise YahooFantasyError("Yahoo OAuth state signature does not match")

    try:
        payload = json.loads(_b64url_decode(encoded))
    except Exception as exc:
        raise YahooFantasyError("Yahoo OAuth state payload is malformed") from exc
    if not isinstance(payload, Mapping):
        raise YahooFantasyError("Yahoo OAuth state payload must be an object")
    if payload.get("purpose") != "fantasy-hq-yahoo":
        raise YahooFantasyError("Yahoo OAuth state purpose does not match")
    issued_at = payload.get("iat")
    if isinstance(issued_at, bool) or not isinstance(issued_at, int):
        raise YahooFantasyError("Yahoo OAuth state timestamp is invalid")
    now = int(time.time() if now_seconds is None else now_seconds)
    if issued_at > now + 60:
        raise YahooFantasyError("Yahoo OAuth state timestamp is in the future")
    if now - issued_at > max_age_seconds:
        raise YahooFantasyError("Yahoo OAuth state has expired")
    nonce = payload.get("nonce")
    if not isinstance(nonce, str) or not nonce:
        raise YahooFantasyError("Yahoo OAuth state nonce is invalid")
    return dict(payload)


class YahooOAuthClient:
    def __init__(
        self,
        config: YahooOAuthConfig,
        *,
        client: httpx.Client | None = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        self.config = config
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=False,
            headers={"Accept": "application/json", "User-Agent": "PropWar-FantasyHQ/1.0"},
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "YahooOAuthClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def exchange_code(self, code: str) -> YahooOAuthToken:
        code = _canonical_text(code, "code")
        return self._token_request(
            {
                "grant_type": "authorization_code",
                "redirect_uri": self.config.redirect_uri,
                "code": code,
            }
        )

    def refresh(self, refresh_token: str) -> YahooOAuthToken:
        refresh_token = _canonical_text(refresh_token, "refresh_token")
        return self._token_request(
            {
                "grant_type": "refresh_token",
                "redirect_uri": self.config.redirect_uri,
                "refresh_token": refresh_token,
            }
        )

    def _token_request(self, data: Mapping[str, str]) -> YahooOAuthToken:
        response = self._client.post(
            YAHOO_TOKEN_URL,
            data=dict(data),
            auth=httpx.BasicAuth(self.config.client_id, self.config.client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if response.status_code != 200:
            raise YahooFantasyError(
                f"Yahoo token request failed with HTTP {response.status_code}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise YahooFantasyError("Yahoo token response was not JSON") from exc
        if not isinstance(payload, Mapping):
            raise YahooFantasyError("Yahoo token response must be an object")

        access_token = payload.get("access_token")
        expires_in = payload.get("expires_in")
        refresh_token = payload.get("refresh_token")
        token_type = payload.get("token_type") or "bearer"
        try:
            expires = int(expires_in)
        except (TypeError, ValueError) as exc:
            raise YahooFantasyError("Yahoo token response has invalid expires_in") from exc
        return YahooOAuthToken(
            access_token=str(access_token or ""),
            refresh_token=(str(refresh_token) if refresh_token else None),
            expires_in=expires,
            token_type=str(token_type),
        )


class YahooFantasyClient:
    def __init__(
        self,
        access_token: str,
        *,
        client: httpx.Client | None = None,
        base_url: str = YAHOO_FANTASY_BASE,
        timeout_seconds: float = 20.0,
    ) -> None:
        token = _canonical_text(access_token, "access_token")
        self._access_token = token
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/") + "/",
            timeout=timeout_seconds,
            follow_redirects=False,
            headers={
                "Accept": "application/json",
                "User-Agent": "PropWar-FantasyHQ/1.0",
            },
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "YahooFantasyClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _get_json(self, path: str) -> Any:
        response = self._client.get(
            path.lstrip("/"),
            params={"format": "json"},
            headers={"Authorization": f"Bearer {self._access_token}"},
        )
        if response.status_code != 200:
            raise YahooFantasyError(
                f"Yahoo Fantasy request failed with HTTP {response.status_code}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise YahooFantasyError("Yahoo Fantasy response was not JSON") from exc
        if not isinstance(payload, Mapping) or "fantasy_content" not in payload:
            raise YahooFantasyError("Yahoo Fantasy response is malformed")
        return payload

    def fetch_user_nfl_teams(self) -> tuple[YahooTeamSummary, ...]:
        payload = self._get_json("users;use_login=1/games;game_keys=nfl/teams")
        teams: list[YahooTeamSummary] = []
        seen: set[str] = set()
        for resource in _resource_nodes(payload, "team"):
            team_key = _first_text(resource, "team_key")
            if not team_key or team_key in seen or ".t." not in team_key:
                continue
            seen.add(team_key)
            name = _first_text(resource, "name") or team_key
            league_key = team_key.rsplit(".t.", 1)[0]
            teams.append(
                YahooTeamSummary(
                    team_key=team_key,
                    league_key=league_key,
                    name=name,
                    team_id=_first_text(resource, "team_id"),
                    url=_first_text(resource, "url"),
                )
            )
        return tuple(teams)

    def fetch_team_roster(self, team_key: str) -> tuple[YahooPlayerSummary, ...]:
        team_key = _canonical_text(team_key, "team_key")
        payload = self._get_json(f"team/{team_key}/roster")
        players: list[YahooPlayerSummary] = []
        seen: set[str] = set()
        for resource in _resource_nodes(payload, "player"):
            player_key = _first_text(resource, "player_key")
            if not player_key or player_key in seen:
                continue
            seen.add(player_key)
            selected = _first_mapping(resource, "selected_position")
            players.append(
                YahooPlayerSummary(
                    player_key=player_key,
                    name=(
                        _first_text(resource, "full")
                        or _first_text(resource, "name")
                        or player_key
                    ),
                    display_position=_first_text(resource, "display_position"),
                    nfl_team=_first_text(resource, "editorial_team_abbr"),
                    selected_position=(
                        _first_text(selected, "position") if selected else None
                    ),
                    status=_first_text(resource, "status"),
                )
            )
        return tuple(players)

    def fetch_league(self, league_key: str) -> YahooLeagueSummary:
        league_key = _canonical_text(league_key, "league_key")
        payload = self._get_json(f"league/{league_key};out=settings")
        resources = tuple(_resource_nodes(payload, "league"))
        if not resources:
            raise YahooFantasyError("Yahoo league metadata is missing")
        resource = resources[0]
        returned_key = _first_text(resource, "league_key")
        if returned_key and returned_key != league_key:
            raise YahooFantasyError("Yahoo returned the wrong league")
        return YahooLeagueSummary(
            league_key=league_key,
            name=_first_text(resource, "name") or league_key,
            season=_first_text(resource, "season"),
            num_teams=_first_int(resource, "num_teams"),
            current_week=_first_int(resource, "current_week"),
            scoring_type=_first_text(resource, "scoring_type"),
            draft_status=_first_text(resource, "draft_status"),
        )


def _resource_nodes(value: Any, key: str) -> Iterable[Any]:
    if isinstance(value, Mapping):
        for current_key, current_value in value.items():
            if current_key == key:
                yield current_value
            yield from _resource_nodes(current_value, key)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _resource_nodes(item, key)


def _first_text(value: Any, key: str) -> str | None:
    for candidate in _values_for_key(value, key):
        if isinstance(candidate, (str, int, float)) and not isinstance(candidate, bool):
            text = str(candidate).strip()
            if text:
                return text
    return None


def _first_int(value: Any, key: str) -> int | None:
    text = _first_text(value, key)
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _first_mapping(value: Any, key: str) -> Mapping[str, Any] | None:
    for candidate in _values_for_key(value, key):
        if isinstance(candidate, Mapping):
            return candidate
    return None


def _values_for_key(value: Any, key: str) -> Iterable[Any]:
    if isinstance(value, Mapping):
        for current_key, current_value in value.items():
            if current_key == key:
                yield current_value
            yield from _values_for_key(current_value, key)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _values_for_key(item, key)


def _canonical_text(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise YahooFantasyError(f"{label} is required")
    if any(ord(char) < 32 or ord(char) == 127 for char in text):
        raise YahooFantasyError(f"{label} contains control characters")
    return text


def _validated_https_origin_path(value: Any) -> str:
    text = _canonical_text(value, "redirect_uri")
    parsed = urlsplit(text)
    if parsed.scheme != "https" or not parsed.hostname:
        raise YahooFantasyError("Yahoo redirect_uri must use HTTPS")
    if parsed.username is not None or parsed.password is not None:
        raise YahooFantasyError("Yahoo redirect_uri must not contain credentials")
    if parsed.fragment:
        raise YahooFantasyError("Yahoo redirect_uri must not contain a fragment")
    return text


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> str:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding).decode("utf-8")
