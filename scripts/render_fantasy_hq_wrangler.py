from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.fantasy.cloudflare_config import write_rendered_wrangler


DEFAULT_TEMPLATE = REPO_ROOT / "workers" / "fantasy-hq" / "wrangler.template.jsonc"
DEFAULT_OUTPUT = REPO_ROOT / "workers" / "fantasy-hq" / "wrangler.generated.jsonc"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render the non-secret Fantasy HQ Wrangler config with a real D1 UUID."
    )
    parser.add_argument("--database-id", required=True, help="Cloudflare D1 database UUID")
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = write_rendered_wrangler(
        template_path=args.template,
        output_path=args.output,
        database_id=args.database_id,
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
