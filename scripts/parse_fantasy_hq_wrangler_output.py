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
    parse_fantasy_hq_wrangler_output,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Parse sanitized Fantasy HQ Wrangler deployment evidence."
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = parse_fantasy_hq_wrangler_output(
            args.output.read_text(encoding="utf-8")
        )
    except (FantasyRemoteCloudflareError, OSError) as exc:
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
            {"ready": True, **result.safe_summary()},
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
