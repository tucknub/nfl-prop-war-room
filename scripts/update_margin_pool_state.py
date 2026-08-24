from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.margin import pool_state


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE = REPO_ROOT / "src" / "margin" / "live_state_2026.json"


def _optional_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    text = value.strip().lower()
    if text in {"true", "yes", "1", "visible"}:
        return True
    if text in {"false", "no", "0", "hidden"}:
        return False
    raise argparse.ArgumentTypeError("expected true/false")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Safely replace the Margin Pool opponent field snapshot."
    )
    parser.add_argument("--field-csv", required=True, type=Path)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pool-name")
    parser.add_argument("--pool-size", type=int)
    parser.add_argument("--tie-rule", choices=["split", "shared"])
    parser.add_argument("--pick-deadline")
    parser.add_argument("--picks-visible", type=_optional_bool)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    state = json.loads(args.state.read_text(encoding="utf-8"))
    opponents = pool_state.load_field_csv(
        args.field_csv,
        completed_week=int(state.get("completed_week", 0) or 0),
    )
    updated, readiness = pool_state.apply_pool_snapshot(
        state,
        opponents,
        pool_name=args.pool_name,
        first_place_tie_rule=args.tie_rule,
        pick_deadline=args.pick_deadline,
        picks_visible_before_deadline=args.picks_visible,
        explicit_pool_size=args.pool_size,
        payout_structure="winner_take_all",
    )

    print(json.dumps({
        "pool_size": updated["pool"]["size"],
        "opponents": len(updated["opponents"]),
        "championship_status": readiness["status"],
        "championship_ready": readiness["ready"],
        "missing": readiness["missing"],
        "invalid": readiness["invalid"],
        "issues": readiness["issues"],
    }, indent=2, sort_keys=True))

    if args.dry_run:
        return

    output = args.output or args.state
    output.write_text(json.dumps(updated, indent=2) + "\n", encoding="utf-8")
    print(f"wrote_state={output}")


if __name__ == "__main__":
    main()
