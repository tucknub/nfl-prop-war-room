from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.rehearse_depthsnap_release import run_rehearsal
from src.export import depthsnap_release as release
from src.export.depthsnap_exporter import (
    DepthSnapExportError,
    registry_spec_from_status,
    validate_registry,
    write_registry,
)


def write_status(
    path: Path,
    state: str,
    *,
    season: int = 2026,
    week: int | None = None,
    message: str | None = None,
) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "season": season,
                "status": state,
                "generated_at_utc": "2026-07-26T00:00:00Z",
                "published_through_week": week,
                "completed_games": 0,
                "message": message or f"Supplied {state} state.",
                "source_status": [],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize("state", ["PRESEASON", "WAITING_FOR_COMPLETED_WEEK"])
def test_nonpublished_states_promote_truthful_empty_registry(
    tmp_path: Path,
    state: str,
) -> None:
    active = tmp_path / "depthsnap" / "export"
    status = write_status(tmp_path / f"{state}.json", state)
    result = release.apply_current_publication(
        status,
        active=active,
        output_dir=tmp_path,
        generated_at="2026-07-26T00:00:00Z",
    )
    assert result["action"] == "promoted_no_published_week"
    validated = validate_registry(active)
    assert validated["publicationStatus"] == "no_published_week"
    assert validated["season"] == 2026
    assert validated["throughWeek"] is None
    assert validated["bundleCount"] == 9


def test_blocked_state_retains_prior_current_registry(tmp_path: Path) -> None:
    active = tmp_path / "depthsnap" / "export"
    waiting = write_status(tmp_path / "waiting.json", "WAITING_FOR_COMPLETED_WEEK")
    write_registry(
        active,
        registry_spec_from_status(
            waiting,
            generated_at="2026-07-26T00:00:00Z",
        ),
    )
    prior = validate_registry(active)
    blocked = write_status(tmp_path / "blocked.json", "BLOCKED")
    result = release.apply_current_publication(
        blocked,
        active=active,
        output_dir=tmp_path,
    )
    assert result["action"] == "retained_prior"
    assert result["sourceVersion"] == prior["sourceVersion"]
    assert validate_registry(active) == prior


def test_blocked_without_current_prior_promotes_supplied_unavailable(
    tmp_path: Path,
) -> None:
    active = tmp_path / "depthsnap" / "export"
    historical_state = write_status(
        tmp_path / "old-season.json",
        "PRESEASON",
        season=2025,
    )
    write_registry(active, registry_spec_from_status(historical_state))
    blocked = write_status(tmp_path / "blocked.json", "BLOCKED")
    result = release.apply_current_publication(
        blocked,
        active=active,
        output_dir=tmp_path,
        generated_at="2026-07-26T00:00:00Z",
    )
    assert result["action"] == "promoted_unavailable"
    validated = validate_registry(active)
    assert validated["publicationStatus"] == "unavailable"
    assert validated["season"] == 2026
    assert validated["bundleCount"] == 9


def test_validated_not_published_never_promotes(tmp_path: Path) -> None:
    active = tmp_path / "depthsnap" / "export"
    status = write_status(tmp_path / "dry-run.json", "VALIDATED_NOT_PUBLISHED")
    result = release.apply_current_publication(
        status,
        active=active,
        output_dir=tmp_path,
    )
    assert result == {
        "action": "not_promoted",
        "operationalState": "VALIDATED_NOT_PUBLISHED",
        "priorRegistryRetained": False,
        "season": 2026,
    }
    assert not active.exists()


def test_published_requires_current_validation_before_promotion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active = tmp_path / "depthsnap" / "export"
    status = write_status(tmp_path / "published.json", "PUBLISHED", week=1)
    supplied_spec = object()
    calls: list[object] = []

    def spec_builder(*args: object, **kwargs: object) -> object:
        calls.append(("spec", args, kwargs))
        return supplied_spec

    def promote(spec: object, active: Path, keep_rollback: bool) -> dict[str, object]:
        calls.append(("promote", spec, active, keep_rollback))
        return {
            "publicationStatus": "published",
            "season": 2026,
            "throughWeek": 1,
            "bundleCount": 42,
            "teamBundles": 32,
            "playerBundles": 1,
            "sourceVersion": "sha256:validated-current",
        }

    monkeypatch.setattr(release, "current_published_registry_spec", spec_builder)
    monkeypatch.setattr(release, "build_and_promote", promote)
    result = release.apply_current_publication(
        status,
        active=active,
        output_dir=tmp_path,
    )
    assert result["action"] == "promoted_published"
    assert calls[0][0] == "spec"
    assert calls[1] == ("promote", supplied_spec, active, True)


def test_published_validation_failure_leaves_prior_registry_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active = tmp_path / "depthsnap" / "export"
    waiting = write_status(tmp_path / "waiting.json", "WAITING_FOR_COMPLETED_WEEK")
    write_registry(active, registry_spec_from_status(waiting))
    prior = validate_registry(active)
    published = write_status(tmp_path / "published.json", "PUBLISHED", week=1)

    def fail_validation(*args: object, **kwargs: object) -> object:
        raise DepthSnapExportError("independent validation failed")

    monkeypatch.setattr(
        release,
        "current_published_registry_spec",
        fail_validation,
    )
    with pytest.raises(DepthSnapExportError, match="independent validation failed"):
        release.apply_current_publication(
            published,
            active=active,
            output_dir=tmp_path,
        )
    assert validate_registry(active) == prior


def test_release_rehearsal_covers_failure_rollback_recovery_and_cleanup() -> None:
    result = run_rehearsal()
    assert result == {
        "explicitRollbackRestoredPrior": True,
        "failedReplacementRetainedPrior": True,
        "finalPublicationStatus": "no_published_week",
        "laterPromotionSucceeded": True,
        "noPartialRegistryObserved": True,
        "rollbackDirectoriesRemoved": 1,
        "stagingDirectoriesRemoved": 1,
    }
