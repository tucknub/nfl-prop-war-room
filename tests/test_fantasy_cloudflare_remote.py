from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.fantasy.cloudflare_config import EXPECTED_D1_DATABASE_NAME, EXPECTED_WORKER_NAME
from src.fantasy.cloudflare_remote import (
    REMOTE_D1_REQUIRED_TABLE_COUNT,
    WRANGLER_PINNED_VERSION,
    FantasyRemoteCloudflareError,
    FantasyRemoteD1NotFound,
    parse_fantasy_hq_wrangler_output,
    select_fantasy_hq_remote_d1,
    verify_fantasy_hq_remote_d1_probe,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "fantasy-hq-shadow-deploy.yml"
RESOLVE_SCRIPT = REPO_ROOT / "scripts" / "resolve_fantasy_hq_remote_d1.py"
VERIFY_SCRIPT = REPO_ROOT / "scripts" / "verify_fantasy_hq_remote_d1.py"
PARSE_SCRIPT = REPO_ROOT / "scripts" / "parse_fantasy_hq_wrangler_output.py"

DB_ID = "11111111-2222-4333-8444-555555555555"
OTHER_ID = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"


def _inventory(*records):
    return list(records)


def _db(name=EXPECTED_D1_DATABASE_NAME, uuid=DB_ID):
    return {"name": name, "uuid": uuid}


def _probe(**overrides):
    row = {
        "required_table_count": REMOTE_D1_REQUIRED_TABLE_COUNT,
        "league_families": 0,
        "league_seasons": 0,
        "state_snapshots": 0,
        "change_events": 0,
        "sync_runs": 0,
    }
    row.update(overrides)
    return [{"results": [row], "success": True, "meta": {"duration": 1}}]


def _wrangler_output(
    *,
    worker_name=EXPECTED_WORKER_NAME,
    version_id="version-123",
    targets=None,
):
    if targets is None:
        targets = ["https://propwar-fantasy-hq.example.workers.dev"]
    return "\n".join(
        [
            json.dumps(
                {
                    "type": "wrangler-session",
                    "version": 1,
                    "wrangler_version": WRANGLER_PINNED_VERSION,
                }
            ),
            json.dumps(
                {
                    "type": "deploy",
                    "version": 1,
                    "worker_name": worker_name,
                    "version_id": version_id,
                    "targets": targets,
                }
            ),
        ]
    )


def test_remote_d1_selection_requires_exact_single_name():
    selection = select_fantasy_hq_remote_d1(
        _inventory(_db(), _db("other", OTHER_ID))
    )

    assert selection.database_id == DB_ID
    assert selection.database_name == EXPECTED_D1_DATABASE_NAME


def test_remote_d1_selection_honors_explicit_uuid_and_name():
    selection = select_fantasy_hq_remote_d1(
        _inventory(_db(), _db("other", OTHER_ID)),
        expected_database_id=DB_ID.upper(),
    )

    assert selection.database_id == DB_ID


def test_remote_d1_selection_rejects_missing_duplicate_or_wrong_name():
    with pytest.raises(FantasyRemoteD1NotFound):
        select_fantasy_hq_remote_d1(_inventory(_db("other", OTHER_ID)))

    with pytest.raises(FantasyRemoteCloudflareError, match="multiple"):
        select_fantasy_hq_remote_d1(_inventory(_db(), _db(uuid=OTHER_ID)))

    with pytest.raises(FantasyRemoteCloudflareError, match="differently named"):
        select_fantasy_hq_remote_d1(
            _inventory(_db("other", DB_ID)),
            expected_database_id=DB_ID,
        )


def test_remote_d1_selection_rejects_malformed_inventory():
    for payload in ({}, "[]", [None], [{"name": "", "uuid": DB_ID}]):
        with pytest.raises(FantasyRemoteCloudflareError):
            select_fantasy_hq_remote_d1(payload)


def test_remote_d1_probe_requires_complete_empty_schema():
    values = verify_fantasy_hq_remote_d1_probe(_probe())

    assert values["required_table_count"] == REMOTE_D1_REQUIRED_TABLE_COUNT
    assert sum(value for key, value in values.items() if key != "required_table_count") == 0


@pytest.mark.parametrize(
    "overrides",
    [
        {"required_table_count": REMOTE_D1_REQUIRED_TABLE_COUNT - 1},
        {"league_families": 1},
        {"league_seasons": 1},
        {"state_snapshots": 1},
        {"change_events": 1},
        {"sync_runs": 1},
    ],
)
def test_remote_d1_probe_fails_closed_on_incomplete_or_used_database(overrides):
    with pytest.raises(FantasyRemoteCloudflareError):
        verify_fantasy_hq_remote_d1_probe(_probe(**overrides))


def test_remote_d1_probe_rejects_shape_or_type_drift():
    bad = _probe()
    bad[0]["results"][0]["extra"] = 0
    with pytest.raises(FantasyRemoteCloudflareError, match="shape"):
        verify_fantasy_hq_remote_d1_probe(bad)

    bad = _probe(league_seasons=True)
    with pytest.raises(FantasyRemoteCloudflareError, match="integer"):
        verify_fantasy_hq_remote_d1_probe(bad)


def test_wrangler_output_requires_exact_workers_dev_deployment():
    result = parse_fantasy_hq_wrangler_output(_wrangler_output())

    assert result.worker_name == EXPECTED_WORKER_NAME
    assert result.version_id == "version-123"
    assert result.worker_url == "https://propwar-fantasy-hq.example.workers.dev"
    assert result.safe_summary() == {
        "worker_name": EXPECTED_WORKER_NAME,
        "version_id": "version-123",
        "worker_url": "https://propwar-fantasy-hq.example.workers.dev",
        "schedule_mode": "SHADOW",
        "cron_count": 0,
    }


@pytest.mark.parametrize(
    "text",
    [
        _wrangler_output(worker_name="wrong-worker"),
        _wrangler_output(targets=["https://example.com"]),
        _wrangler_output(targets=["http://propwar-fantasy-hq.example.workers.dev"]),
        _wrangler_output(targets=["https://wrong.example.workers.dev"]),
        _wrangler_output(targets=[]),
        _wrangler_output(targets=[
            "https://propwar-fantasy-hq.example.workers.dev",
            "https://propwar-fantasy-hq.other.workers.dev",
        ]),
    ],
)
def test_wrangler_output_rejects_target_or_identity_drift(text):
    with pytest.raises(FantasyRemoteCloudflareError):
        parse_fantasy_hq_wrangler_output(text)


def test_wrangler_output_rejects_failed_or_ambiguous_deploy_records():
    failure = json.dumps({"type": "command-failed", "version": 1}) + "\n" + _wrangler_output()
    with pytest.raises(FantasyRemoteCloudflareError, match="failed"):
        parse_fantasy_hq_wrangler_output(failure)

    duplicate = _wrangler_output() + "\n" + json.dumps(
        {
            "type": "deploy",
            "worker_name": EXPECTED_WORKER_NAME,
            "version_id": "version-456",
            "targets": ["https://propwar-fantasy-hq.example.workers.dev"],
        }
    )
    with pytest.raises(FantasyRemoteCloudflareError, match="exactly one"):
        parse_fantasy_hq_wrangler_output(duplicate)


def test_remote_helper_scripts_emit_only_bounded_results(tmp_path: Path):
    inventory = tmp_path / "inventory.json"
    inventory.write_text(json.dumps([_db()]), encoding="utf-8")

    resolved = subprocess.run(
        [sys.executable, str(RESOLVE_SCRIPT), "--inventory", str(inventory)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert resolved.returncode == 0
    assert resolved.stdout.strip() == DB_ID
    assert resolved.stderr == ""

    probe = tmp_path / "probe.json"
    probe.write_text(json.dumps(_probe()), encoding="utf-8")
    verified = subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT), "--probe", str(probe)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert verified.returncode == 0
    assert json.loads(verified.stdout) == {
        "ready": True,
        "schema_ready": True,
        "empty_persistence_state": True,
        "required_table_count": REMOTE_D1_REQUIRED_TABLE_COUNT,
    }

    output = tmp_path / "wrangler.ndjson"
    output.write_text(_wrangler_output(), encoding="utf-8")
    parsed = subprocess.run(
        [sys.executable, str(PARSE_SCRIPT), "--output", str(output)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert parsed.returncode == 0
    payload = json.loads(parsed.stdout)
    assert payload["ready"] is True
    assert payload["worker_url"].endswith(".workers.dev")
    assert payload["cron_count"] == 0


def test_remote_resolver_uses_distinct_not_found_exit_code(tmp_path: Path):
    inventory = tmp_path / "inventory.json"
    inventory.write_text(json.dumps([]), encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, str(RESOLVE_SCRIPT), "--inventory", str(inventory)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert completed.returncode == 3
    assert completed.stdout == ""
    assert json.loads(completed.stderr) == {
        "ready": False,
        "error_type": "FantasyRemoteD1NotFound",
    }


def test_shadow_deploy_workflow_is_manual_only_and_fail_closed():
    text = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "\n  schedule:" not in text
    assert "DEPLOY_FANTASY_HQ_SHADOW" in text
    assert "create_database_if_missing:" in text
    assert "default: false" in text
    assert 'WRANGLER_VERSION: "4.125.0"' in text
    assert WRANGLER_PINNED_VERSION == "4.125.0"

    for secret_name in (
        "CLOUDFLARE_API_TOKEN",
        "CLOUDFLARE_ACCOUNT_ID",
        "FANTASY_PERSISTENCE_TOKEN",
    ):
        assert f"secrets.{secret_name}" in text

    assert "d1 migrations apply FANTASY_DB" in text
    assert "--remote --config" in text
    assert "verify_fantasy_hq_remote_d1.py" in text
    assert "deploy \\" in text
    assert "--dry-run --secrets-file" in text
    assert "WRANGLER_OUTPUT_FILE_PATH=" in text
    assert "parse_fantasy_hq_wrangler_output.py" in text
    assert "/workers/scripts/propwar-fantasy-hq/schedules" in text
    assert 'result.get("schedules") != []' in text
    assert "check_fantasy_hq_runtime_handshake.py" in text
    assert '"real_fantasy_write_performed": False' in text


def test_shadow_deploy_workflow_never_uploads_secret_or_raw_wrangler_artifacts():
    text = WORKFLOW_PATH.read_text(encoding="utf-8")

    upload_section = text.split("- name: Upload sanitized evidence", 1)[1]
    assert "fantasy-hq-shadow-deployment-evidence.json" in upload_section
    assert "wrangler-output.ndjson" not in upload_section
    assert "fantasy-hq-secrets.env" not in upload_section
    assert "d1-inventory" not in upload_section
