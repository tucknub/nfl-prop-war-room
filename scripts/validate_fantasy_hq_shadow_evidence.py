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
    validate_fantasy_hq_shadow_deployment_evidence,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the exact shadow deployment evidence required before a real canary."
    )
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--expected-run-id", type=int, required=True)
    parser.add_argument("--expected-commit-sha", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        evidence = validate_fantasy_hq_shadow_deployment_evidence(
            load_json_file(args.evidence),
            expected_run_id=args.expected_run_id,
            expected_commit_sha=args.expected_commit_sha,
        )
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
            evidence.safe_summary(),
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
