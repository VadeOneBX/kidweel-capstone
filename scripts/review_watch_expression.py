"""Dry-run operator review for WATCH spread expressions (no paper submit)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from qops.risk.watch_promotion_review import run_watch_promotion_review
from qops.runtime.orb_manifest import immutable_manifest_path, read_manifest_by_run_id


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review WATCH expression for operator promotion.")
    parser.add_argument("--base-dir", default=".", help="Repository root")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-date", default=None, help="YYYY-MM-DD (defaults from run-id prefix)")
    parser.add_argument("--expression-id", required=True)
    parser.add_argument("--decision", choices=("approve", "reject"), required=True)
    parser.add_argument("--reason", default="", help="Operator approval/rejection reason")
    parser.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Default true: evaluate only; use --no-dry-run to append watch_promotion_review.csv",
    )
    return parser.parse_args()


def _run_date_from_run_id(run_id: str) -> str:
    if len(run_id) >= 10 and run_id[4] == "-" and run_id[7] == "-":
        return run_id[:10]
    raise ValueError(f"run_date_required: cannot parse from run_id {run_id}")


def main() -> int:
    args = parse_args()
    base_dir = Path(args.base_dir).resolve()
    run_date = args.run_date or _run_date_from_run_id(args.run_id)

    manifest_path = immutable_manifest_path(base_dir, run_date, args.run_id)
    if not manifest_path.is_file():
        print(f"NO_MANIFEST_FOUND: {manifest_path}")
        return 1

    manifest = read_manifest_by_run_id(base_dir, run_date, args.run_id)
    candidates_path = Path(manifest.candidates_artifact) if manifest.candidates_artifact else None
    expressions_path = Path(manifest.expressions_artifact) if manifest.expressions_artifact else None

    result = run_watch_promotion_review(
        base_dir=base_dir,
        run_id=args.run_id,
        run_date=run_date,
        expression_id=args.expression_id,
        operator_decision=args.decision,
        operator_reason=args.reason,
        live_mode_enabled=bool(manifest.live_mode_enabled),
        broker_mutation_occurred=bool(manifest.broker_mutation_occurred),
        expressions_path=expressions_path,
        candidates_path=candidates_path,
        dry_run=bool(args.dry_run),
    )

    payload = {
        "promotion_status": result.promotion_status,
        "promotion_block_reason": result.promotion_block_reason,
        "paper_route_status": result.paper_route_status,
        "expression_status": result.expression_status,
        "candidate_loop_status": result.candidate_loop_status,
        "broker_mutation_occurred": result.broker_mutation_occurred,
        "dry_run": bool(args.dry_run),
        "review_row": result.review_row,
    }
    print(json.dumps(payload, indent=2))
    return 0 if result.promotion_status in {
        "WATCH_OPERATOR_APPROVED",
        "WATCH_OPERATOR_REJECTED",
    } else 2


if __name__ == "__main__":
    raise SystemExit(main())
