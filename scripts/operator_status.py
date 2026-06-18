from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from qops.runtime.orb_manifest import manifest_path, read_manifest, read_manifest_by_run_id


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dir", default=".")
    parser.add_argument("--date", default=None)
    parser.add_argument(
        "--run-id",
        default=None,
        help="Read immutable manifest for this run_id instead of latest orb_manifest.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_dir = Path(args.base_dir).resolve()

    run_date = args.date or datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")

    if args.run_id:
        path = base_dir / "data" / "runs" / run_date / f"{args.run_id}_orb_manifest.json"
        if not path.exists():
            print(f"NO_MANIFEST_FOUND: {path}")
            return 1
        print(read_manifest_by_run_id(base_dir, run_date, args.run_id).model_dump_json(indent=2))
        return 0

    path = manifest_path(base_dir, run_date)
    if not path.exists():
        print(f"NO_MANIFEST_FOUND: {path}")
        return 1

    print(read_manifest(base_dir, run_date).model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
