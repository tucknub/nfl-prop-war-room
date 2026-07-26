from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.export.depthsnap_exporter import (  # noqa: E402
    ACTIVE_EXPORT_DIRECTORY,
    HISTORICAL_EXPORT_DIRECTORY,
    DepthSnapExportError,
    active_registry_spec,
    build_and_promote,
    cleanup_registry_artifacts,
    historical_registry_spec,
    registry_spec_from_status,
    rollback_registry,
    validate_registry,
    write_opportunity_context_preservation_report,
    write_registry,
)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Build and manage deterministic DepthSnap Python export registries."
    )
    commands = root.add_subparsers(dest="command", required=True)

    active = commands.add_parser(
        "build-active",
        help="Build the truthful active operational registry and optionally promote it.",
    )
    active.add_argument("--generated-at")
    active.add_argument("--output", type=Path)
    active.add_argument("--promote", action="store_true")
    active.add_argument("--discard-rollback", action="store_true")

    historical = commands.add_parser(
        "build-historical",
        help="Build the authorized completed-2025 historical parity registry.",
    )
    historical.add_argument("--generated-at")
    historical.add_argument(
        "--output", type=Path, default=HISTORICAL_EXPORT_DIRECTORY
    )
    historical.add_argument("--replace", action="store_true")

    supplied = commands.add_parser(
        "build-from-status",
        help="Build a non-published registry from a supplied operational status artifact.",
    )
    supplied.add_argument("status_path", type=Path)
    supplied.add_argument("--generated-at")
    supplied.add_argument("--output", type=Path, required=True)
    supplied.add_argument("--replace", action="store_true")

    validate = commands.add_parser("validate", help="Run Python registry validation.")
    validate.add_argument("directory", type=Path)

    rollback = commands.add_parser("rollback", help="Swap active and rollback registries.")
    rollback.add_argument("--active", type=Path, default=ACTIVE_EXPORT_DIRECTORY)

    cleanup = commands.add_parser("cleanup", help="Remove stale staging artifacts.")
    cleanup.add_argument("--active", type=Path, default=ACTIVE_EXPORT_DIRECTORY)
    cleanup.add_argument("--remove-rollback", action="store_true")

    preservation = commands.add_parser(
        "preserve-context",
        help="Write the private Opportunity Context preservation inventory.",
    )
    preservation.add_argument("output", type=Path)
    return root


def main() -> None:
    arguments = parser().parse_args()
    if arguments.command == "build-active":
        spec = active_registry_spec(arguments.generated_at)
        if arguments.promote:
            if arguments.output is not None:
                raise DepthSnapExportError("--output cannot be combined with --promote")
            result = build_and_promote(
                spec,
                keep_rollback=not arguments.discard_rollback,
            )
        else:
            output = arguments.output or ACTIVE_EXPORT_DIRECTORY
            result = write_registry(output, spec, replace=True)
    elif arguments.command == "build-historical":
        result = write_registry(
            arguments.output,
            historical_registry_spec(arguments.generated_at),
            replace=arguments.replace,
        )
    elif arguments.command == "build-from-status":
        result = write_registry(
            arguments.output,
            registry_spec_from_status(
                arguments.status_path, generated_at=arguments.generated_at
            ),
            replace=arguments.replace,
        )
    elif arguments.command == "validate":
        result = validate_registry(arguments.directory)
    elif arguments.command == "rollback":
        result = rollback_registry(arguments.active)
    elif arguments.command == "cleanup":
        result = cleanup_registry_artifacts(
            arguments.active, remove_rollback=arguments.remove_rollback
        )
    else:
        result = write_opportunity_context_preservation_report(arguments.output)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except DepthSnapExportError as exc:
        print(f"DepthSnap export failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
