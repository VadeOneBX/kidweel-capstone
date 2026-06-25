"""Generate operator advisory markdown from an existing morning run (ADVISORY-VOICE-C1)."""

from __future__ import annotations

import argparse
from pathlib import Path

from qops.advisory.operator_advisory import generate_operator_advisory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build data/processed/<run_id>_operator_advisory.md")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--base-dir", default=".")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_dir = Path(args.base_dir).resolve()
    result = generate_operator_advisory(base_dir, args.run_id)
    print(result.operator_advisory_artifact)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
