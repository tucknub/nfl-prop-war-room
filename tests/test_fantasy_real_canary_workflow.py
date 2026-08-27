from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from src.fantasy.cloudflare_config import EXPECTED_WORKER_NAME
from src.fantasy.cloudflare_remote import (
    FantasyRemoteCloudflareError,
    validate_fantasy_hq_shadow_deployment_evidence,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
CANARY_WORKFLOW = (
    REPO_ROOT / ".github" / "workflows" / "fantasy-hq-single-league-canary.yml"
)
SHADOW_WORKFLOW = (
    REPO_ROOT / ".github" / "workflows" / "fantasy-hq-shadow-deploy.yml"
)
VALIDATE_SHADOW_SCRIPT = (
    REPO_ROOT / "scripts" / "validate_fantasy_hq_shadow_evidence.py"
)

DB_ID = "11111111-2222-4333-8444-555555555555"
RUN_ID = 123456789
COMMIT_SHA = "a" * 40
WORKER_URL = "https://propwar-fantasy-hq.example.workers.dev"


def _handshake() -> dict:
    return {
        "authenticated_read_ready": True,
        "handshake_version": 1,
        "health_ready": True,
        "probe_absent": True,
        "protocol_version": 1,
        "ready": True,
        "write_enabled": False,
    }


def _shadow_evidence(**overrides) -> dict:
    payload = {
        "ready": True,
        "deployment_mode": "SHADOW",
        "worker_name": EXPECTED_WORKER_NAME,
        "worker_url": WORKER_URL,
        "version_id": "version-123",
        "database_id": DB_ID,
        "source_run_id": RUN_ID,
        "source_commit_sha": COMMIT_SHA,
        "source_ref": "streamlit-cloud-deploy",
        "cron_count": 0,
        "d1_schema_ready": True,
        "d1_empty_persistence_state": True,
        "health": {"ok": True, "status": "ok", "protocol_version": 1},
        "runtime_handshake": _handshake(),
        "real_fantasy_write_performed": False,
    }
    payload.update(overrides)
    return payload


def test_shadow_evidence_handoff_requires_exact_run_commit_and_ready_state():
    result = validate_fantasy_hq_shadow_deployment_evidence(
        _shadow_evidence(),
        expected_run_id=RUN_ID,
        expected_commit_sha=COMMIT_SHA,
    )

    assert result.database_id == DB_ID
    assert result.worker_url == WORKER_URL
    assert result.version_id == "version-123"
    assert result.source_run_id == RUN_ID
    assert result.source_commit_sha == COMMIT_SHA
    assert result.source_ref == "streamlit-cloud-deploy"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"expected_run_id": RUN_ID + 1, "expected_commit_sha": COMMIT_SHA},
        {"expected_run_id": RUN_ID, "expected_commit_sha": "b" * 40},
    ],
)
def test_shadow_evidence_handoff_rejects_wrong_provenance(kwargs):
    with pytest.raises(FantasyRemoteCloudflareError):
        validate_fantasy_hq_shadow_deployment_evidence(
            _shadow_evidence(),
            **kwargs,
        )


@pytest.mark.parametrize(
    "mutation",
    [
        {"ready": False},
        {"deployment_mode": "LIVE"},
        {"worker_name": "wrong-worker"},
        {"cron_count": 1},
        {"d1_schema_ready": False},
        {"d1_empty_persistence_state": False},
        {"real_fantasy_write_performed": True},
        {"source_ref": "other-branch"},
        {"source_run_id": 0},
        {"source_commit_sha": "not-a-sha"},
        {"health": {"ok": True, "status": "ok", "protocol_version": 2}},
        {"runtime_handshake": {**_handshake(), "write_enabled": True}},
    ],
)
def test_shadow_evidence_handoff_fails_closed_on_readiness_drift(mutation):
    with pytest.raises(FantasyRemoteCloudflareError):
        validate_fantasy_hq_shadow_deployment_evidence(
            _shadow_evidence(**mutation),
            expected_run_id=RUN_ID,
            expected_commit_sha=COMMIT_SHA,
        )


def test_shadow_evidence_handoff_rejects_shape_drift():
    payload = _shadow_evidence()
    payload["unexpected"] = "private-data"

    with pytest.raises(FantasyRemoteCloudflareError, match="shape"):
        validate_fantasy_hq_shadow_deployment_evidence(payload)


def test_shadow_evidence_validator_cli_is_sanitized(tmp_path: Path):
    evidence = tmp_path / "evidence.json"
    payload = _shadow_evidence()
    payload["unexpected"] = "do-not-print-this"
    evidence.write_text(json.dumps(payload), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(VALIDATE_SHADOW_SCRIPT),
            "--evidence",
            str(evidence),
            "--expected-run-id",
            str(RUN_ID),
            "--expected-commit-sha",
            COMMIT_SHA,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert completed.returncode == 1
    assert completed.stdout == ""
    assert json.loads(completed.stderr) == {
        "ready": False,
        "error_type": "FantasyRemoteCloudflareError",
    }
    assert "do-not-print-this" not in completed.stderr


def test_shadow_workflow_evidence_contains_canary_handoff_identity():
    text = SHADOW_WORKFLOW.read_text(encoding="utf-8")

    assert '"database_id": os.environ["DATABASE_ID"]' in text
    assert '"source_run_id": int(os.environ["GITHUB_RUN_ID"])' in text
    assert '"source_commit_sha": os.environ["GITHUB_SHA"]' in text
    assert '"source_ref": os.environ["GITHUB_REF_NAME"]' in text


def test_real_canary_workflow_is_valid_manual_only_yaml():
    text = CANARY_WORKFLOW.read_text(encoding="utf-8")

    assert yaml.compose(text) is not None
    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "\n  schedule:" not in text
    assert "\n  workflow_run:" not in text


def test_real_canary_workflow_defaults_to_preview_and_requires_reviewed_identity():
    text = CANARY_WORKFLOW.read_text(encoding="utf-8")

    assert 'default: "PREVIEW_ONLY"' in text
    assert "EXECUTE_ONE_WRITE" in text
    assert "RUN_ONE_REAL_FANTASY_WRITE" in text
    assert "expected_sync_run_id:" in text
    assert 'test "$EXPECTED_SYNC_RUN_ID" = "$ACTUAL_SYNC_RUN_ID"' in text
    assert "preview_fantasy_hq_single_league_canary.py" in text
    assert "run_fantasy_hq_single_league_canary.py" in text
    assert "First pristine canary must produce ACCEPTED" in text


def test_real_canary_workflow_requires_exact_shadow_artifact_and_commit():
    text = CANARY_WORKFLOW.read_text(encoding="utf-8")

    assert "actions: read" in text
    assert "actions/download-artifact@v4" in text
    assert "fantasy-hq-shadow-deployment-evidence" in text
    assert "github-token: ${{ github.token }}" in text
    assert "run-id: ${{ inputs.shadow_run_id }}" in text
    assert "validate_fantasy_hq_shadow_evidence.py" in text
    assert '--expected-commit-sha "$GITHUB_SHA"' in text


def test_real_canary_workflow_rechecks_remote_state_before_any_write():
    text = CANARY_WORKFLOW.read_text(encoding="utf-8")

    preview_index = text.index("- name: Build deterministic canary preview")
    execute_index = text.index("- name: Execute exactly one real canary write")

    for required in (
        "Re-verify remote D1 is still pristine",
        "verify_fantasy_hq_remote_d1.py",
        "Re-verify remote Cron Triggers are empty",
        "/workers/scripts/propwar-fantasy-hq/schedules",
        "Re-run authenticated read-only runtime handshake",
        "check_fantasy_hq_runtime_handshake.py",
    ):
        assert required in text
        assert text.index(required) < preview_index < execute_index


def test_real_canary_workflow_cannot_deploy_migrate_create_or_schedule():
    text = CANARY_WORKFLOW.read_text(encoding="utf-8")

    forbidden = (
        "wrangler@$WRANGLER_VERSION deploy",
        "d1 migrations apply",
        "d1 create",
        "secret put",
        "triggers:",
        "crons:",
    )
    for token in forbidden:
        assert token not in text


def test_real_canary_identity_is_never_a_public_workflow_input():
    text = CANARY_WORKFLOW.read_text(encoding="utf-8")

    input_block = text.split("permissions:", 1)[0]
    for name in (
        "league_season_id:",
        "platform_league_id:",
        "league_family_id:",
        "family_display_name:",
        "season_display_name:",
        "registration_created_at_ms:",
        "current_user_id:",
    ):
        assert name not in input_block

    for name in (
        "FANTASY_CANARY_LEAGUE_SEASON_ID",
        "FANTASY_CANARY_PLATFORM_LEAGUE_ID",
        "FANTASY_CANARY_SEASON",
        "FANTASY_CANARY_LEAGUE_FAMILY_ID",
        "FANTASY_CANARY_FAMILY_DISPLAY_NAME",
        "FANTASY_CANARY_SEASON_DISPLAY_NAME",
        "FANTASY_CANARY_REGISTRATION_CREATED_AT_MS",
        "FANTASY_CANARY_CURRENT_USER_ID",
    ):
        assert f"secrets.{name}" in text


def test_real_canary_public_evidence_uses_only_identity_fingerprint():
    text = CANARY_WORKFLOW.read_text(encoding="utf-8")

    assert "league_identity_fingerprint" in text
    assert 'preview["league_season_id"]' not in text
    assert 'preview["platform_league_id"]' not in text

    publish = text.split("- name: Publish successful canary evidence", 1)[1]
    assert "FANTASY_CANARY_CURRENT_USER_ID" not in publish
    assert "FANTASY_CANARY_PLATFORM_LEAGUE_ID" not in publish


def test_real_canary_failure_path_preserves_no_retry_warning():
    text = CANARY_WORKFLOW.read_text(encoding="utf-8")

    assert "continue-on-error: true" in text
    assert "fantasy-hq-single-league-canary-failure" in text
    assert "Do not retry automatically" in text
