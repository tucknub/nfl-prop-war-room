from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.export.depthsnap_exporter import (
    DepthSnapExportError,
    build_and_promote,
    cleanup_registry_artifacts,
    promote_staged_registry,
    registry_spec_from_status,
    rollback_registry,
    staging_directory,
    validate_registry,
    write_registry,
)


def _write_status(path: Path, state: str, message: str) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "season": 2026,
                "status": state,
                "generated_at_utc": "2026-07-26T00:00:00Z",
                "published_through_week": None,
                "completed_games": 0,
                "message": message,
                "source_status": [],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def run_rehearsal() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="depthsnap-release-rehearsal-") as root:
        directory = Path(root)
        active = directory / "depthsnap" / "export"
        initial_status = directory / "initial.json"
        replacement_status = directory / "replacement.json"
        later_status = directory / "later.json"
        _write_status(initial_status, "PRESEASON", "Initial valid preseason registry.")
        _write_status(
            replacement_status,
            "WAITING_FOR_COMPLETED_WEEK",
            "Replacement awaits a completed week.",
        )
        _write_status(
            later_status,
            "WAITING_FOR_COMPLETED_WEEK",
            "Later valid replacement.",
        )

        initial = build_and_promote(
            registry_spec_from_status(
                initial_status,
                generated_at="2026-07-26T00:00:00Z",
            ),
            active=active,
        )
        initial_version = initial["sourceVersion"]

        invalid_stage = staging_directory(active)
        write_registry(
            invalid_stage,
            registry_spec_from_status(
                replacement_status,
                generated_at="2026-07-27T00:00:00Z",
            ),
        )
        (invalid_stage / "home.json").write_text("{}\n", encoding="utf-8")
        failed_closed = False
        try:
            promote_staged_registry(invalid_stage, active)
        except DepthSnapExportError:
            failed_closed = True
        if not failed_closed or validate_registry(active)["sourceVersion"] != initial_version:
            raise DepthSnapExportError("Failed replacement did not retain the prior registry")

        replacement = build_and_promote(
            registry_spec_from_status(
                replacement_status,
                generated_at="2026-07-27T00:00:00Z",
            ),
            active=active,
        )
        replacement_version = replacement["sourceVersion"]
        rolled_back = rollback_registry(active)
        if rolled_back["sourceVersion"] != initial_version:
            raise DepthSnapExportError("Explicit rollback did not restore the initial registry")

        promoted = build_and_promote(
            registry_spec_from_status(
                later_status,
                generated_at="2026-07-28T00:00:00Z",
            ),
            active=active,
        )
        if promoted["sourceVersion"] in {initial_version, replacement_version}:
            raise DepthSnapExportError("Later promotion did not produce a distinct registry")
        cleanup = cleanup_registry_artifacts(active, remove_rollback=True)
        final = validate_registry(active)
        return {
            "failedReplacementRetainedPrior": failed_closed,
            "explicitRollbackRestoredPrior": True,
            "laterPromotionSucceeded": True,
            "noPartialRegistryObserved": True,
            "finalPublicationStatus": final["publicationStatus"],
            "stagingDirectoriesRemoved": cleanup["stagingDirectoriesRemoved"],
            "rollbackDirectoriesRemoved": cleanup["rollbackDirectoriesRemoved"],
        }


if __name__ == "__main__":
    print(json.dumps(run_rehearsal(), indent=2, sort_keys=True))
