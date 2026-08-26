from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from .changes import FantasySnapshot
from .models import FantasyLeagueState, LeagueTransaction


MAX_NFL_REGULAR_WEEK = 18


class UnsafeSleeperCurrentSnapshot(ValueError):
    """Raised when current Sleeper state cannot form a trustworthy snapshot window."""


@dataclass(frozen=True)
class SleeperNflState:
    season: str
    league_season: str
    season_type: str
    week: int
    leg: int
    display_week: int | None = None
    season_start_date: str | None = None
    previous_season: str | None = None
    league_create_season: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "season", _text(self.season, "season"))
        object.__setattr__(
            self, "league_season", _text(self.league_season, "league_season")
        )
        object.__setattr__(
            self, "season_type", _text(self.season_type, "season_type")
        )
        object.__setattr__(self, "week", _nonnegative_int(self.week, "week"))
        object.__setattr__(self, "leg", _nonnegative_int(self.leg, "leg"))
        if self.display_week is not None:
            object.__setattr__(
                self,
                "display_week",
                _nonnegative_int(self.display_week, "display_week"),
            )
        for field_name in (
            "season_start_date",
            "previous_season",
            "league_create_season",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    _text(value, field_name),
                )


@dataclass(frozen=True)
class SleeperCurrentSnapshotResult:
    snapshot: FantasySnapshot
    nfl_state: SleeperNflState
    transaction_rounds: tuple[int, ...]

    @property
    def current_transaction_round(self) -> int | None:
        return self.transaction_rounds[-1] if self.transaction_rounds else None

    @property
    def provider_status(self) -> str:
        return "HEALTHY"

    @property
    def source_metadata(self) -> Mapping[str, Any]:
        return {
            "provider": "SLEEPER",
            "nfl_state": {
                "season": self.nfl_state.season,
                "league_season": self.nfl_state.league_season,
                "season_type": self.nfl_state.season_type,
                "week": self.nfl_state.week,
                "leg": self.nfl_state.leg,
                "display_week": self.nfl_state.display_week,
            },
            "transaction_round": self.current_transaction_round,
            "transaction_rounds_fetched": list(self.transaction_rounds),
        }


class SleeperCurrentSnapshotReader(Protocol):
    def fetch_normalized_league(
        self,
        league_id: str,
        *,
        current_user_id: str | None = None,
    ) -> FantasyLeagueState: ...

    def fetch_transactions(
        self,
        league_id: str,
        week: int,
    ) -> tuple[LeagueTransaction, ...]: ...


def normalize_sleeper_nfl_state(payload: Any) -> SleeperNflState:
    if not isinstance(payload, Mapping):
        raise UnsafeSleeperCurrentSnapshot(
            "Sleeper returned malformed NFL state"
        )

    return SleeperNflState(
        season=_text(payload.get("season"), "season"),
        league_season=_text(payload.get("league_season"), "league_season"),
        season_type=_text(payload.get("season_type"), "season_type"),
        week=_nonnegative_int(payload.get("week"), "week"),
        leg=_nonnegative_int(payload.get("leg"), "leg"),
        display_week=_optional_nonnegative_int(
            payload.get("display_week"), "display_week"
        ),
        season_start_date=_optional_text(
            payload.get("season_start_date"), "season_start_date"
        ),
        previous_season=_optional_text(
            payload.get("previous_season"), "previous_season"
        ),
        league_create_season=_optional_text(
            payload.get("league_create_season"), "league_create_season"
        ),
    )


def build_current_sleeper_snapshot(
    reader: SleeperCurrentSnapshotReader,
    league_id: str,
    *,
    snapshot_id: str,
    current_user_id: str | None,
    nfl_state: SleeperNflState,
    previous_snapshot: FantasySnapshot | None = None,
    previous_transaction_round: int | None = None,
) -> SleeperCurrentSnapshotResult:
    """Fetch one normalized current Sleeper snapshot with deterministic tx catch-up.

    The NFL state is caller-supplied so one state/nfl request can be shared
    across multiple leagues. Transaction rounds use Sleeper's leg field, not
    preseason/display week.

    For an ownership-ready league with prior ownership-ready state, the current
    fetch overlaps the prior transaction round. This preserves pending-to-complete
    transitions and catches every intervening round after downtime.
    """

    normalized_league_id = _text(league_id, "league_id")
    normalized_snapshot_id = _text(snapshot_id, "snapshot_id")
    state = reader.fetch_normalized_league(
        normalized_league_id,
        current_user_id=current_user_id,
    )
    _validate_current_league(state, normalized_league_id, nfl_state)
    _validate_previous_snapshot(state, previous_snapshot)

    rounds = _transaction_rounds(
        state,
        nfl_state,
        previous_snapshot=previous_snapshot,
        previous_transaction_round=previous_transaction_round,
    )
    transactions = _fetch_transaction_window(
        reader,
        normalized_league_id,
        rounds,
    )

    return SleeperCurrentSnapshotResult(
        snapshot=FantasySnapshot(
            snapshot_id=normalized_snapshot_id,
            league=state,
            transactions=transactions,
        ),
        nfl_state=nfl_state,
        transaction_rounds=rounds,
    )


def _validate_current_league(
    state: FantasyLeagueState,
    requested_league_id: str,
    nfl_state: SleeperNflState,
) -> None:
    if state.platform.upper() != "SLEEPER":
        raise UnsafeSleeperCurrentSnapshot(
            "current Sleeper snapshot requires SLEEPER league state"
        )
    if state.platform_league_id != requested_league_id:
        raise UnsafeSleeperCurrentSnapshot(
            "normalized league ID does not match requested Sleeper league"
        )
    if state.season not in {nfl_state.season, nfl_state.league_season}:
        raise UnsafeSleeperCurrentSnapshot(
            "Sleeper NFL state does not match the league season"
        )


def _validate_previous_snapshot(
    current: FantasyLeagueState,
    previous: FantasySnapshot | None,
) -> None:
    if previous is None:
        return
    before = previous.league
    if (
        before.platform,
        before.platform_league_id,
        before.season,
    ) != (
        current.platform,
        current.platform_league_id,
        current.season,
    ):
        raise UnsafeSleeperCurrentSnapshot(
            "previous snapshot belongs to a different league or season"
        )
    if before.ownership_ready and not current.ownership_ready:
        raise UnsafeSleeperCurrentSnapshot(
            "current ownership readiness regressed"
        )


def _transaction_rounds(
    state: FantasyLeagueState,
    nfl_state: SleeperNflState,
    *,
    previous_snapshot: FantasySnapshot | None,
    previous_transaction_round: int | None,
) -> tuple[int, ...]:
    if not state.ownership_ready:
        return ()

    current_round = nfl_state.leg
    if current_round < 1 or current_round > MAX_NFL_REGULAR_WEEK:
        raise UnsafeSleeperCurrentSnapshot(
            "ownership-ready league requires a valid Sleeper NFL leg 1-18"
        )

    if previous_snapshot is None or not previous_snapshot.league.ownership_ready:
        return (current_round,)

    prior_round = previous_transaction_round
    if prior_round is None:
        prior_weeks = tuple(
            tx.week
            for tx in previous_snapshot.transactions
            if tx.week is not None
        )
        if not prior_weeks:
            raise UnsafeSleeperCurrentSnapshot(
                "previous_transaction_round is required when prior ownership-ready "
                "snapshot has no transaction week evidence"
            )
        prior_round = max(prior_weeks)

    prior_round = _positive_regular_week(
        prior_round,
        "previous_transaction_round",
    )
    if prior_round > current_round:
        raise UnsafeSleeperCurrentSnapshot(
            "previous transaction round cannot exceed current Sleeper NFL leg"
        )

    return tuple(range(prior_round, current_round + 1))


def _fetch_transaction_window(
    reader: SleeperCurrentSnapshotReader,
    league_id: str,
    rounds: tuple[int, ...],
) -> tuple[LeagueTransaction, ...]:
    by_id: dict[str, LeagueTransaction] = {}
    for week in rounds:
        for transaction in reader.fetch_transactions(league_id, week):
            transaction_id = transaction.platform_transaction_id
            prior = by_id.get(transaction_id)
            if prior is not None and prior != transaction:
                raise UnsafeSleeperCurrentSnapshot(
                    "Sleeper returned conflicting rows for one transaction ID"
                )
            by_id[transaction_id] = transaction

    return tuple(
        sorted(
            by_id.values(),
            key=lambda tx: (
                tx.week if tx.week is not None else MAX_NFL_REGULAR_WEEK + 1,
                tx.created_at_ms if tx.created_at_ms is not None else -1,
                tx.platform_transaction_id,
            ),
        )
    )


def _positive_regular_week(value: Any, label: str) -> int:
    week = _nonnegative_int(value, label)
    if week < 1 or week > MAX_NFL_REGULAR_WEEK:
        raise UnsafeSleeperCurrentSnapshot(
            f"{label} must be between 1 and {MAX_NFL_REGULAR_WEEK}"
        )
    return week


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise UnsafeSleeperCurrentSnapshot(
            f"{label} must be a nonblank canonical string"
        )
    return value


def _optional_text(value: Any, label: str) -> str | None:
    return None if value is None else _text(value, label)


def _nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise UnsafeSleeperCurrentSnapshot(
            f"{label} must be a non-negative integer"
        )
    return value


def _optional_nonnegative_int(value: Any, label: str) -> int | None:
    return None if value is None else _nonnegative_int(value, label)
