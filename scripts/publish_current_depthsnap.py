from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.export.depthsnap_exporter import (  # noqa: E402
    ACTIVE_EXPORT_DIRECTORY,
    CURRENT_ROLE_OUTPUT_DIRECTORY,
    DepthSnapExportError,
)
from src.export.depthsnap_release import apply_current_publication  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply one validated current-season operational state to DepthSnap."
    )
    parser.add_argument("status_path", type=Path)
    parser.add_argument("--active", type=Path, default=ACTIVE_EXPORT_DIRECTORY)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=CURRENT_ROLE_OUTPUT_DIRECTORY,
    )
    parser.add_argument("--generated-at")
    arguments = parser.parse_args()
    result = apply_current_publication(
        arguments.status_path,
        active=arguments.active,
        output_dir=arguments.output_dir,
        generated_at=arguments.generated_at,
    )
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except DepthSnapExportError as exc:
        print(f"DepthSnap current publication failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
