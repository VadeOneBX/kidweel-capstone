from __future__ import annotations

import argparse
from pathlib import Path

from qops.ingest.ingestion_wake import run_ingestion_wake


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--mode",
        choices=["orb-watchdog", "orb-final", "manual"],
        default="manual",
    )

    parser.add_argument(
        "--base-dir",
        default=".",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
    )

    parser.add_argument(
        "--live",
        action="store_true",
        help="Forbidden. Present only to fail closed if accidentally passed.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.live:
        raise RuntimeError("LIVE_MODE_FORBIDDEN: scheduler cannot enable live execution.")

    base_dir = Path(args.base_dir).resolve()

    manifest = run_ingestion_wake(
        base_dir=base_dir,
        mode=args.mode,
        dry_run=args.dry_run,
    )

    print(manifest.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
