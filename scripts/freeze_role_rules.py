from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from role_validation.config import config_sha256, load_config


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    config = load_config(args.config)
    config["status"]["rules_frozen_for_2025"] = True
    config["status"]["frozen_at_utc"] = datetime.now(timezone.utc).isoformat()
    config["status"]["frozen_config_sha256"] = config_sha256(config)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(config, handle, sort_keys=False)

    print(f"Frozen rules written to {output}")
    print(f"SHA-256: {config['status']['frozen_config_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
