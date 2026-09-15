from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.operations.published_validation import validate_published_role_outputs  # noqa: E402


def _json_default(value: object) -> object:
    """Convert scalar objects from pandas/numpy validation results to JSON-safe values."""
    item = getattr(value, "item", None)
    if callable(item):
        converted = item()
        if converted is not value:
            return converted
    if isinstance(value, Path):
        return str(value)
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


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
    rendered = json.dumps(report, indent=2, default=_json_default)
    args.report_dir.mkdir(parents=True, exist_ok=True)
    path = args.report_dir / f"published_role_validation_{args.season}.json"
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(rendered + "\n", encoding="utf-8")
    temporary.replace(path)
    print(rendered)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
