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
    load_json_file,
    verify_fantasy_hq_remote_d1_probe,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the read-only post-migration Fantasy HQ remote D1 probe."
    )
    parser.add_argument("--probe", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        values = verify_fantasy_hq_remote_d1_probe(load_json_file(args.probe))
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

    print(
        json.dumps(
            {
                "ready": True,
                "schema_ready": True,
                "empty_persistence_state": True,
                "required_table_count": values["required_table_count"],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
