from __future__ import annotations

import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any, Mapping


DATABASE_ID_PLACEHOLDER = "__FANTASY_D1_DATABASE_ID__"
EXPECTED_WORKER_NAME = "propwar-fantasy-hq"
EXPECTED_MAIN = "./index.mjs"
EXPECTED_COMPATIBILITY_DATE = "2026-08-26"
EXPECTED_SECRET_NAME = "FANTASY_PERSISTENCE_TOKEN"
EXPECTED_SCHEDULE_MODE = "SHADOW"
EXPECTED_CRONS: tuple[str, ...] = ()
EXPECTED_D1_BINDING = "FANTASY_DB"
EXPECTED_D1_DATABASE_NAME = "propwar-fantasy-hq"
EXPECTED_MIGRATIONS_DIR = "../../migrations"


class UnsafeFantasyCloudflareConfig(ValueError):
    """Raised when a deployment config would violate Fantasy HQ invariants."""


def canonical_d1_database_id(value: Any) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise UnsafeFantasyCloudflareConfig(
            "D1 database ID must be a non-empty UUID without surrounding whitespace"
        )
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError) as exc:
        raise UnsafeFantasyCloudflareConfig("D1 database ID must be a valid UUID") from exc
    if parsed.int == 0:
        raise UnsafeFantasyCloudflareConfig("D1 database ID must not be the nil UUID")
    return str(parsed)


def render_fantasy_hq_wrangler(template_text: str, database_id: str) -> str:
    if not isinstance(template_text, str) or not template_text.strip():
        raise UnsafeFantasyCloudflareConfig("Wrangler template must be non-empty text")
    if template_text.count(DATABASE_ID_PLACEHOLDER) != 1:
        raise UnsafeFantasyCloudflareConfig(
            "Wrangler template must contain exactly one D1 database ID placeholder"
        )

    canonical_id = canonical_d1_database_id(database_id)
    rendered = template_text.replace(DATABASE_ID_PLACEHOLDER, canonical_id)
    try:
        config = json.loads(rendered)
    except json.JSONDecodeError as exc:
        raise UnsafeFantasyCloudflareConfig("Rendered Wrangler config must be valid JSON") from exc

    validate_fantasy_hq_wrangler(config, expected_database_id=canonical_id)
    return rendered.rstrip() + "\n"


def validate_fantasy_hq_wrangler(
    config: Mapping[str, Any],
    *,
    expected_database_id: str,
) -> None:
    if not isinstance(config, Mapping):
        raise UnsafeFantasyCloudflareConfig("Wrangler config must be a JSON object")

    expected_scalars = {
        "name": EXPECTED_WORKER_NAME,
        "main": EXPECTED_MAIN,
        "compatibility_date": EXPECTED_COMPATIBILITY_DATE,
        "workers_dev": True,
    }
    for key, expected in expected_scalars.items():
        if config.get(key) != expected:
            raise UnsafeFantasyCloudflareConfig(f"Wrangler config {key} invariant changed")

    observability = config.get("observability")
    if observability != {"enabled": True, "head_sampling_rate": 1}:
        raise UnsafeFantasyCloudflareConfig("Wrangler observability invariant changed")

    secrets = config.get("secrets")
    if secrets != {"required": [EXPECTED_SECRET_NAME]}:
        raise UnsafeFantasyCloudflareConfig("Wrangler required-secret declaration changed")

    vars_block = config.get("vars")
    if vars_block != {"FANTASY_SCHEDULE_MODE": EXPECTED_SCHEDULE_MODE}:
        raise UnsafeFantasyCloudflareConfig(
            "Wrangler schedule-mode invariant changed"
        )
    if EXPECTED_SECRET_NAME in vars_block:
        raise UnsafeFantasyCloudflareConfig(
            "FANTASY_PERSISTENCE_TOKEN must never be stored in Wrangler vars"
        )

    triggers = config.get("triggers")
    if triggers != {"crons": list(EXPECTED_CRONS)}:
        raise UnsafeFantasyCloudflareConfig(
            "Wrangler cron triggers must remain disabled in shadow deployment config"
        )

    databases = config.get("d1_databases")
    if not isinstance(databases, list) or len(databases) != 1:
        raise UnsafeFantasyCloudflareConfig("Wrangler config must define exactly one D1 database")
    database = databases[0]
    if not isinstance(database, Mapping):
        raise UnsafeFantasyCloudflareConfig("D1 binding must be an object")

    expected_database = {
        "binding": EXPECTED_D1_BINDING,
        "database_name": EXPECTED_D1_DATABASE_NAME,
        "database_id": canonical_d1_database_id(expected_database_id),
        "migrations_dir": EXPECTED_MIGRATIONS_DIR,
    }
    if dict(database) != expected_database:
        raise UnsafeFantasyCloudflareConfig("Wrangler D1 binding invariant changed")


def write_rendered_wrangler(
    *,
    template_path: Path,
    output_path: Path,
    database_id: str,
) -> Path:
    template_text = template_path.read_text(encoding="utf-8")
    rendered = render_fantasy_hq_wrangler(template_text, database_id)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{output_path.name}.",
        suffix=".tmp",
        dir=output_path.parent,
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, output_path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise
    return output_path
