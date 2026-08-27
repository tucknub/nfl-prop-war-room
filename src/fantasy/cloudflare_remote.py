from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

from .cloudflare_config import (
    EXPECTED_D1_DATABASE_NAME,
    EXPECTED_WORKER_NAME,
    canonical_d1_database_id,
)


WRANGLER_PINNED_VERSION = "4.125.0"
REMOTE_D1_REQUIRED_TABLE_COUNT = 8


class FantasyRemoteCloudflareError(RuntimeError):
    """Remote Cloudflare deployment evidence is unsafe or inconsistent."""


class FantasyRemoteD1NotFound(FantasyRemoteCloudflareError):
    """The intended D1 database does not exist in the inspected account."""


@dataclass(frozen=True)
class FantasyRemoteD1Selection:
    database_id: str
    database_name: str = EXPECTED_D1_DATABASE_NAME

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "database_id",
            canonical_d1_database_id(self.database_id),
        )
        if self.database_name != EXPECTED_D1_DATABASE_NAME:
            raise FantasyRemoteCloudflareError(
                "remote D1 selection does not match Fantasy HQ database name"
            )


@dataclass(frozen=True)
class FantasyRemoteDeployResult:
    worker_name: str
    version_id: str
    worker_url: str

    def __post_init__(self) -> None:
        if self.worker_name != EXPECTED_WORKER_NAME:
            raise FantasyRemoteCloudflareError(
                "remote deployment worker name does not match Fantasy HQ"
            )
        if not _canonical_text(self.version_id):
            raise FantasyRemoteCloudflareError(
                "remote deployment version ID must be canonical text"
            )
        object.__setattr__(
            self,
            "worker_url",
            _validated_workers_dev_url(self.worker_url),
        )

    def safe_summary(self) -> dict[str, Any]:
        return {
            "worker_name": self.worker_name,
            "version_id": self.version_id,
            "worker_url": self.worker_url,
            "schedule_mode": "SHADOW",
            "cron_count": 0,
        }


def select_fantasy_hq_remote_d1(
    payload: Any,
    *,
    expected_database_id: str | None = None,
) -> FantasyRemoteD1Selection:
    """Select exactly one intended D1 resource from Wrangler JSON inventory.

    Exact UUID input is authoritative when supplied. Otherwise exactly one
    database with the fixed Fantasy HQ name must exist. Ambiguity always fails
    closed.
    """

    if not isinstance(payload, Sequence) or isinstance(
        payload, (str, bytes, bytearray)
    ):
        raise FantasyRemoteCloudflareError("D1 inventory must be a JSON array")

    records: list[tuple[str, str]] = []
    for index, raw in enumerate(payload):
        if not isinstance(raw, Mapping):
            raise FantasyRemoteCloudflareError(
                f"D1 inventory record {index} must be an object"
            )
        name = raw.get("name")
        if not _canonical_text(name):
            raise FantasyRemoteCloudflareError(
                f"D1 inventory record {index} has invalid name"
            )
        raw_id = raw.get("uuid", raw.get("database_id"))
        try:
            database_id = canonical_d1_database_id(raw_id)
        except Exception as exc:
            raise FantasyRemoteCloudflareError(
                f"D1 inventory record {index} has invalid UUID"
            ) from exc
        records.append((name, database_id))

    if expected_database_id is not None:
        expected = canonical_d1_database_id(expected_database_id)
        matches = [(name, dbid) for name, dbid in records if dbid == expected]
        if not matches:
            raise FantasyRemoteD1NotFound(
                "explicit Fantasy HQ D1 UUID is not present in the Cloudflare account"
            )
        if len(matches) != 1:
            raise FantasyRemoteCloudflareError(
                "explicit Fantasy HQ D1 UUID is duplicated in Cloudflare inventory"
            )
        name, database_id = matches[0]
        if name != EXPECTED_D1_DATABASE_NAME:
            raise FantasyRemoteCloudflareError(
                "explicit D1 UUID belongs to a differently named database"
            )
        return FantasyRemoteD1Selection(database_id=database_id)

    matches = [
        (name, database_id)
        for name, database_id in records
        if name == EXPECTED_D1_DATABASE_NAME
    ]
    if not matches:
        raise FantasyRemoteD1NotFound(
            "Fantasy HQ D1 database is not present in the Cloudflare account"
        )
    if len(matches) != 1:
        raise FantasyRemoteCloudflareError(
            "multiple Fantasy HQ D1 databases share the expected name"
        )
    return FantasyRemoteD1Selection(database_id=matches[0][1])


def verify_fantasy_hq_remote_d1_probe(payload: Any) -> dict[str, int]:
    """Validate the post-migration remote D1 read-only probe.

    The first production canary requires an empty persistence dataset. Existing
    fantasy rows fail closed so a previously-used database cannot silently be
    treated as a fresh first-write target.
    """

    if not isinstance(payload, list) or len(payload) != 1:
        raise FantasyRemoteCloudflareError(
            "remote D1 probe must contain exactly one query result"
        )
    result = payload[0]
    if not isinstance(result, Mapping) or result.get("success") is not True:
        raise FantasyRemoteCloudflareError("remote D1 probe did not succeed")
    rows = result.get("results")
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], Mapping):
        raise FantasyRemoteCloudflareError(
            "remote D1 probe must return exactly one result row"
        )

    expected_keys = {
        "required_table_count",
        "league_families",
        "league_seasons",
        "state_snapshots",
        "change_events",
        "sync_runs",
    }
    row = rows[0]
    if set(row) != expected_keys:
        raise FantasyRemoteCloudflareError(
            "remote D1 probe returned an unexpected result shape"
        )

    values: dict[str, int] = {}
    for key in sorted(expected_keys):
        value = row[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise FantasyRemoteCloudflareError(
                f"remote D1 probe field {key} must be a non-negative integer"
            )
        values[key] = value

    if values["required_table_count"] != REMOTE_D1_REQUIRED_TABLE_COUNT:
        raise FantasyRemoteCloudflareError(
            "remote D1 schema does not contain the complete Fantasy HQ table set"
        )
    for key in (
        "league_families",
        "league_seasons",
        "state_snapshots",
        "change_events",
        "sync_runs",
    ):
        if values[key] != 0:
            raise FantasyRemoteCloudflareError(
                "remote D1 already contains Fantasy HQ persistence rows"
            )
    return values


def parse_fantasy_hq_wrangler_output(text: str) -> FantasyRemoteDeployResult:
    """Parse Wrangler NDJSON output and require one safe workers.dev deployment."""

    if not isinstance(text, str) or not text.strip():
        raise FantasyRemoteCloudflareError("Wrangler output file is empty")

    deploy_records: list[Mapping[str, Any]] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise FantasyRemoteCloudflareError(
                f"Wrangler output line {line_number} is not valid JSON"
            ) from exc
        if not isinstance(record, Mapping):
            raise FantasyRemoteCloudflareError(
                f"Wrangler output line {line_number} must be an object"
            )
        if record.get("type") == "command-failed":
            raise FantasyRemoteCloudflareError(
                "Wrangler output records a failed deployment command"
            )
        if record.get("type") == "deploy":
            deploy_records.append(record)

    if len(deploy_records) != 1:
        raise FantasyRemoteCloudflareError(
            "Wrangler output must contain exactly one deploy record"
        )

    deploy = deploy_records[0]
    worker_name = deploy.get("worker_name")
    version_id = deploy.get("version_id")
    targets = deploy.get("targets")
    if worker_name != EXPECTED_WORKER_NAME:
        raise FantasyRemoteCloudflareError(
            "Wrangler deployed an unexpected Worker name"
        )
    if not _canonical_text(version_id):
        raise FantasyRemoteCloudflareError(
            "Wrangler deploy record has invalid version ID"
        )
    if not isinstance(targets, list) or len(targets) != 1:
        raise FantasyRemoteCloudflareError(
            "Wrangler deploy must expose exactly one workers.dev target"
        )
    return FantasyRemoteDeployResult(
        worker_name=worker_name,
        version_id=version_id,
        worker_url=targets[0],
    )


def load_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _validated_workers_dev_url(value: Any) -> str:
    if not _canonical_text(value):
        raise FantasyRemoteCloudflareError(
            "Worker deployment target must be canonical text"
        )
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise FantasyRemoteCloudflareError(
            "Worker deployment target must be an HTTPS URL"
        )
    hostname = parsed.hostname.lower()
    if not hostname.endswith(".workers.dev"):
        raise FantasyRemoteCloudflareError(
            "Worker deployment target must remain on workers.dev"
        )
    if hostname.split(".", 1)[0] != EXPECTED_WORKER_NAME:
        raise FantasyRemoteCloudflareError(
            "workers.dev hostname does not match Fantasy HQ Worker name"
        )
    if parsed.port is not None or parsed.username is not None or parsed.password is not None:
        raise FantasyRemoteCloudflareError(
            "Worker deployment target must not contain authority extras"
        )
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise FantasyRemoteCloudflareError(
            "Worker deployment target must be an origin URL"
        )
    return f"https://{hostname}"


def _canonical_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value) and value == value.strip()
