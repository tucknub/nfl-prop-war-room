from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.fantasy.cloudflare_remote import (
    FantasyRemoteCloudflareError,
    FantasyRemoteD1NotFound,
    load_json_file,
    select_fantasy_hq_remote_d1,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve exactly one Fantasy HQ D1 database from Wrangler JSON inventory."
    )
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--expected-id")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        selection = select_fantasy_hq_remote_d1(
            load_json_file(args.inventory),
            expected_database_id=(args.expected_id or None),
        )
    except FantasyRemoteD1NotFound:
        print(
            json.dumps(
                {"ready": False, "error_type": "FantasyRemoteD1NotFound"},
                sort_keys=True,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        return 3
    except (FantasyRemoteCloudflareError, OSError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {"ready": False, "error_type": type(exc).__name__},
                sort_keys=True,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        return 1

    print(selection.database_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
