from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.fantasy.canary import (
    FantasySingleLeagueCanaryError,
    run_single_league_persistence_canary_from_env,
)


def main() -> int:
    try:
        result = run_single_league_persistence_canary_from_env()
    except Exception as exc:
        payload = {
            "ready": False,
            "error_type": type(exc).__name__,
        }
        if isinstance(exc, FantasySingleLeagueCanaryError):
            payload["stage"] = exc.stage
            payload["write_may_have_committed"] = exc.write_may_have_committed
        print(
            json.dumps(payload, sort_keys=True, separators=(",", ":")),
            file=sys.stderr,
        )
        return 1

    print(
        json.dumps(
            result.safe_summary(),
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
