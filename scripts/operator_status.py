from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from qops.runtime.orb_manifest import manifest_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dir", default=".")
    parser.add_argument("--date", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_dir = Path(args.base_dir).resolve()

    run_date = args.date or datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    path = manifest_path(base_dir, run_date)

    if not path.exists():
        print(f"NO_MANIFEST_FOUND: {path}")
        return 1

    print(path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
