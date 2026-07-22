from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.operations.published_validation import validate_published_role_outputs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a published current-season PropWar role partition.")
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs" / "role_research")
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=ROOT / "outputs" / "run_reports" / "role_research",
    )
    args = parser.parse_args()

    report = validate_published_role_outputs(args.season, args.output_dir)
    args.report_dir.mkdir(parents=True, exist_ok=True)
    path = args.report_dir / f"published_role_validation_{args.season}.json"
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
