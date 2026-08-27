from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import os
from typing import Any, Mapping

from .persistence import LeagueSeasonIdentity, canonical_json
from .persistence_http import (
    FantasyPersistenceClientConfig,
    FantasyPersistenceHttpClient,
)
from .persistence_protocol import JAVASCRIPT_MAX_SAFE_INTEGER

from .persistence_rehydrate import rehydrate_latest_snapshot_read
from .runtime_entrypoint import (
    FantasyScheduledRuntimeClient,
    FantasyScheduledRuntimeResult,
    run_handshake_gated_scheduled_sleeper_sync,
)
from .scheduled_sync import (
    SleeperScheduledLeague,
    build_sleeper_scheduled_sync_plan,
)
from .sleeper import SleeperClient
from .sleeper_multi_persistence import SleeperMultiPersistenceReader
from .sleeper_persistence import (
    SLEEPER_PERSIST_ACCEPTED,
    SLEEPER_PERSIST_EXISTING_FINAL,
    SLEEPER_PERSIST_FAILED,
    SLEEPER_PERSIST_NO_CHANGE,
)


FANTASY_SINGLE_LEAGUE_CANARY_VERSION = 1
FANTASY_SINGLE_LEAGUE_CANARY_SCHEDULE_NAME = "fantasy-hq-single-league-canary"
FANTASY_SINGLE_LEAGUE_CANARY_CONFIRMATION = "RUN_ONE_REAL_FANTASY_WRITE"




@dataclass(frozen=True)
class FantasySingleLeagueCanaryConfig:
    """Explicit environment-backed configuration for one real canary write."""

    league: SleeperScheduledLeague
    canary_at_ms: int
    current_user_id: str

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        require_confirmation: bool = True,
    ) -> "FantasySingleLeagueCanaryConfig":
        env = os.environ if environ is None else environ

        if require_confirmation:
            confirmation = _required_env_text(env, "FANTASY_CANARY_CONFIRM")
            if confirmation != FANTASY_SINGLE_LEAGUE_CANARY_CONFIRMATION:
                raise ValueError(
                    "FANTASY_CANARY_CONFIRM must explicitly authorize one real fantasy write"
                )

        season = _required_env_text(env, "FANTASY_CANARY_SEASON")
        identity = LeagueSeasonIdentity(
            league_season_id=_required_env_text(
                env, "FANTASY_CANARY_LEAGUE_SEASON_ID"
            ),
            platform="SLEEPER",
            platform_league_id=_required_env_text(
                env, "FANTASY_CANARY_PLATFORM_LEAGUE_ID"
            ),
            season=season,
        )
        league = SleeperScheduledLeague(
            identity=identity,
            league_family_id=_required_env_text(
                env, "FANTASY_CANARY_LEAGUE_FAMILY_ID"
            ),
            family_display_name=_required_env_text(
                env, "FANTASY_CANARY_FAMILY_DISPLAY_NAME"
            ),
            season_display_name=_required_env_text(
                env, "FANTASY_CANARY_SEASON_DISPLAY_NAME"
            ),
            registration_created_at_ms=_required_env_int(
                env, "FANTASY_CANARY_REGISTRATION_CREATED_AT_MS"
            ),
            request_metadata={"operator_entrypoint": "ENV_CANARY"},
        )
        canary_at_ms = _required_env_int(env, "FANTASY_CANARY_AT_MS")
        if league.registration_created_at_ms > canary_at_ms:
            raise ValueError(
                "FANTASY_CANARY_REGISTRATION_CREATED_AT_MS cannot follow FANTASY_CANARY_AT_MS"
            )
        return cls(
            league=league,
            canary_at_ms=canary_at_ms,
            current_user_id=_required_env_text(
                env, "FANTASY_CANARY_CURRENT_USER_ID"
            ),
        )


class FantasySingleLeagueCanaryError(RuntimeError):
    """Fail-closed canary verification error with sanitized stage metadata."""

    def __init__(
        self,
        message: str,
        *,
        stage: str,
        write_may_have_committed: bool,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.write_may_have_committed = bool(write_may_have_committed)


@dataclass(frozen=True)
class FantasySingleLeagueCanaryResult:
    """Verified one-league persistence canary result."""

    runtime: FantasyScheduledRuntimeResult
    sync_run_id: str
    accepted_snapshot_id: str
    content_fingerprint: str
    mode: str
    readback_verified: bool = True

    def __post_init__(self) -> None:
        if self.runtime.ready is not True:
            raise ValueError("canary result requires a READY runtime handshake")
        if self.mode not in {SLEEPER_PERSIST_ACCEPTED, SLEEPER_PERSIST_NO_CHANGE}:
            raise ValueError("canary result requires ACCEPTED or NO_CHANGE mode")
        for name in ("sync_run_id", "accepted_snapshot_id", "content_fingerprint"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value or value != value.strip():
                raise ValueError(f"{name} must be a nonblank canonical string")
        if self.readback_verified is not True:
            raise ValueError("canary result requires verified read-back")

    @property
    def ready(self) -> bool:
        return True

    @property
    def batch_id(self) -> str:
        return self.runtime.batch_id

    def safe_summary(self) -> dict[str, Any]:
        return {
            "ready": True,
            "canary_version": FANTASY_SINGLE_LEAGUE_CANARY_VERSION,
            "mode": self.mode,
            "readback_verified": True,
            "batch_id": self.batch_id,
            "sync_run_id": self.sync_run_id,
            "accepted_snapshot_id": self.accepted_snapshot_id,
            "content_fingerprint": self.content_fingerprint,
        }


def run_single_league_persistence_canary(
    reader: SleeperMultiPersistenceReader,
    client: FantasyScheduledRuntimeClient,
    league: SleeperScheduledLeague,
    *,
    canary_at_ms: int,
    current_user_id: str | None,
) -> FantasySingleLeagueCanaryResult:
    """Persist one verified Sleeper league once, read it back, and stop.

    This is intentionally a one-league, one-slot runtime canary. The #79
    handshake gate runs before any Sleeper provider read or persistence lifecycle.
    After the persistence result returns, this function performs authenticated
    read-back of both the sync run and latest accepted snapshot and compares the
    rehydrated persisted fingerprint to the exact fingerprint produced by the
    live provider run.

    No verification failure is retried automatically. A post-persistence
    verification failure may mean the write already committed and must be
    inspected via recovery reads before any operator rerun.
    """

    if not isinstance(league, SleeperScheduledLeague):
        raise TypeError("league must be a SleeperScheduledLeague")

    tagged_league = _canary_league(league)
    runtime = run_handshake_gated_scheduled_sleeper_sync(
        reader,
        client,
        (tagged_league,),
        scheduled_at_ms=canary_at_ms,
        current_user_id=current_user_id,
        schedule_name=FANTASY_SINGLE_LEAGUE_CANARY_SCHEDULE_NAME,
    )

    plan = runtime.scheduled.plan
    if plan.league_count != 1 or len(runtime.scheduled.result.leagues) != 1:
        raise FantasySingleLeagueCanaryError(
            "single-league canary returned an unexpected league count",
            stage="RUNTIME_RESULT",
            write_may_have_committed=True,
        )

    planned_spec = plan.specs[0]
    league_outcome = runtime.scheduled.result.leagues[0]
    if league_outcome.spec != planned_spec:
        raise FantasySingleLeagueCanaryError(
            "single-league canary result does not match the frozen plan",
            stage="RUNTIME_RESULT",
            write_may_have_committed=True,
        )

    run_result = league_outcome.result
    if run_result is None:
        raise FantasySingleLeagueCanaryError(
            "single-league canary persistence outcome is unresolved",
            stage="PERSISTENCE_RESULT",
            write_may_have_committed=True,
        )
    if run_result.mode == SLEEPER_PERSIST_EXISTING_FINAL:
        raise FantasySingleLeagueCanaryError(
            "single-league canary slot is already final; use a fresh canary timestamp",
            stage="CANARY_SLOT",
            write_may_have_committed=False,
        )
    if run_result.mode == SLEEPER_PERSIST_FAILED:
        raise FantasySingleLeagueCanaryError(
            "single-league canary provider run failed",
            stage="PERSISTENCE_RESULT",
            write_may_have_committed=True,
        )
    if run_result.mode not in {SLEEPER_PERSIST_ACCEPTED, SLEEPER_PERSIST_NO_CHANGE}:
        raise FantasySingleLeagueCanaryError(
            "single-league canary returned an unsupported mode",
            stage="PERSISTENCE_RESULT",
            write_may_have_committed=True,
        )

    expected_snapshot_id = run_result.accepted_snapshot_id
    expected_fingerprint = run_result.current_content_fingerprint
    if not _canonical_text(expected_snapshot_id) or not _canonical_text(
        expected_fingerprint
    ):
        raise FantasySingleLeagueCanaryError(
            "single-league canary did not expose accepted content identity",
            stage="PERSISTENCE_RESULT",
            write_may_have_committed=True,
        )

    sync_payload = client.read_sync_run(planned_spec.sync_run_id)
    _verify_sync_readback(
        sync_payload,
        sync_run_id=planned_spec.sync_run_id,
        league_season_id=planned_spec.identity.league_season_id,
        accepted_snapshot_id=expected_snapshot_id,
    )

    snapshot_payload = client.read_latest_snapshot(
        planned_spec.identity.league_season_id
    )
    persisted = rehydrate_latest_snapshot_read(snapshot_payload)
    if persisted is None:
        raise FantasySingleLeagueCanaryError(
            "single-league canary latest snapshot is missing after persistence",
            stage="SNAPSHOT_READBACK",
            write_may_have_committed=True,
        )
    if persisted.league_season_id != planned_spec.identity.league_season_id:
        raise FantasySingleLeagueCanaryError(
            "single-league canary read-back belongs to the wrong league season",
            stage="SNAPSHOT_READBACK",
            write_may_have_committed=True,
        )
    if persisted.snapshot.snapshot_id != expected_snapshot_id:
        raise FantasySingleLeagueCanaryError(
            "single-league canary read-back snapshot ID does not match accepted ID",
            stage="SNAPSHOT_READBACK",
            write_may_have_committed=True,
        )
    if persisted.content_fingerprint != expected_fingerprint:
        raise FantasySingleLeagueCanaryError(
            "single-league canary read-back fingerprint does not match live content",
            stage="SNAPSHOT_READBACK",
            write_may_have_committed=True,
        )

    actual_identity = (
        persisted.snapshot.league.platform,
        persisted.snapshot.league.platform_league_id,
        persisted.snapshot.league.season,
    )
    expected_identity = (
        planned_spec.identity.platform,
        planned_spec.identity.platform_league_id,
        planned_spec.identity.season,
    )
    if actual_identity != expected_identity:
        raise FantasySingleLeagueCanaryError(
            "single-league canary read-back league identity does not match plan",
            stage="SNAPSHOT_READBACK",
            write_may_have_committed=True,
        )

    return FantasySingleLeagueCanaryResult(
        runtime=runtime,
        sync_run_id=planned_spec.sync_run_id,
        accepted_snapshot_id=expected_snapshot_id,
        content_fingerprint=expected_fingerprint,
        mode=run_result.mode,
    )


def preview_single_league_persistence_canary_from_env(
    *,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Validate and summarize the exact deterministic canary plan without I/O."""

    config = FantasySingleLeagueCanaryConfig.from_env(
        environ,
        require_confirmation=False,
    )
    tagged_league = _canary_league(config.league)
    plan = build_sleeper_scheduled_sync_plan(
        (tagged_league,),
        scheduled_at_ms=config.canary_at_ms,
        schedule_name=FANTASY_SINGLE_LEAGUE_CANARY_SCHEDULE_NAME,
    )
    spec = plan.specs[0]
    identity_fingerprint = sha256(
        canonical_json(
            {
                "league_season_id": spec.identity.league_season_id,
                "platform": spec.identity.platform,
                "platform_league_id": spec.identity.platform_league_id,
                "season": spec.identity.season,
                "league_family_id": spec.league_family_id,
            }
        ).encode("utf-8")
    ).hexdigest()
    return {
        "ready": True,
        "canary_version": FANTASY_SINGLE_LEAGUE_CANARY_VERSION,
        "platform": spec.identity.platform,
        "season": spec.identity.season,
        "league_identity_fingerprint": identity_fingerprint,
        "canary_at_ms": config.canary_at_ms,
        "batch_id": plan.batch_id,
        "sync_run_id": spec.sync_run_id,
        "snapshot_id": spec.snapshot_id,
        "execution_mode": "CANARY",
    }


def run_single_league_persistence_canary_from_env(
    *,
    environ: Mapping[str, str] | None = None,
) -> FantasySingleLeagueCanaryResult:
    """Execute the one-write canary from explicit runtime environment settings."""

    canary_config = FantasySingleLeagueCanaryConfig.from_env(environ)
    persistence_config = _persistence_config_from_env(environ)

    with SleeperClient() as reader:
        with FantasyPersistenceHttpClient(persistence_config) as client:
            return run_single_league_persistence_canary(
                reader,
                client,
                canary_config.league,
                canary_at_ms=canary_config.canary_at_ms,
                current_user_id=canary_config.current_user_id,
            )


def _canary_league(league: SleeperScheduledLeague) -> SleeperScheduledLeague:
    metadata = dict(league.request_metadata or {})
    if "execution_mode" in metadata or "canary_version" in metadata:
        raise ValueError(
            "canary request metadata cannot predefine execution_mode or canary_version"
        )
    metadata.update(
        {
            "execution_mode": "CANARY",
            "canary_version": FANTASY_SINGLE_LEAGUE_CANARY_VERSION,
        }
    )
    return replace(league, request_metadata=metadata)


def _verify_sync_readback(
    payload: Mapping[str, Any],
    *,
    sync_run_id: str,
    league_season_id: str,
    accepted_snapshot_id: str,
) -> None:
    if not isinstance(payload, Mapping):
        raise FantasySingleLeagueCanaryError(
            "single-league canary sync read-back is not a mapping",
            stage="SYNC_READBACK",
            write_may_have_committed=True,
        )
    if payload.get("found") is not True or not isinstance(payload.get("record"), Mapping):
        raise FantasySingleLeagueCanaryError(
            "single-league canary sync run is missing after persistence",
            stage="SYNC_READBACK",
            write_may_have_committed=True,
        )

    record = payload["record"]
    expected = {
        "sync_run_id": sync_run_id,
        "league_season_id": league_season_id,
        "status": "COMPLETED",
        "accepted_snapshot_id": accepted_snapshot_id,
    }
    for key, value in expected.items():
        if record.get(key) != value:
            raise FantasySingleLeagueCanaryError(
                f"single-league canary sync read-back {key} does not match",
                stage="SYNC_READBACK",
                write_may_have_committed=True,
            )


def _canonical_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value) and value == value.strip()


def _required_env_text(env: Mapping[str, str], name: str) -> str:
    value = env.get(name)
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be a nonblank canonical string")
    return value


def _required_env_int(env: Mapping[str, str], name: str) -> int:
    text = _required_env_text(env, name)
    if not text.isdigit():
        raise ValueError(f"{name} must be a non-negative integer")
    value = int(text)
    if value > JAVASCRIPT_MAX_SAFE_INTEGER:
        raise ValueError(f"{name} exceeds JavaScript safe integer range")
    return value


def _persistence_config_from_env(
    environ: Mapping[str, str] | None,
) -> FantasyPersistenceClientConfig:
    if environ is None:
        return FantasyPersistenceClientConfig.from_env()
    return FantasyPersistenceClientConfig(
        endpoint=_required_env_text(environ, "FANTASY_PERSISTENCE_URL"),
        token=_required_env_text(environ, "FANTASY_PERSISTENCE_TOKEN"),
    )
