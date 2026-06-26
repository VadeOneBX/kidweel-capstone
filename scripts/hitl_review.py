"""Operator CLI for HITL paper transport approvals (no automatic broker submit)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from qops.execution.hitl_paper_transport import (
    apply_operator_decision,
    list_pending_approvals,
)
from qops.schemas.hitl import (
    STATUS_APPROVAL_REQUIRED,
    STATUS_APPROVED_BY_OPERATOR,
    STATUS_REJECTED_BY_OPERATOR,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review pending HITL paper transport approvals.")
    parser.add_argument("--base-dir", default=".", help="Repository root")
    parser.add_argument("--candidate-id", default=None, help="Candidate / payload id")
    parser.add_argument("--decision", choices=("approve", "reject"), default=None)
    parser.add_argument("--reason", default="", help="Operator approval/rejection reason")
    parser.add_argument("--list-pending", action="store_true", help="List pending approvals")
    return parser.parse_args()


def _cli_payload(
    *,
    ok: bool,
    status: str,
    candidate_id: str,
    paper_submit_allowed: bool,
) -> dict[str, object]:
    return {
        "ok": ok,
        "status": status,
        "candidate_id": candidate_id,
        "paper_submit_allowed": paper_submit_allowed,
    }


def main() -> int:
    args = parse_args()
    base_dir = Path(args.base_dir).resolve()

    if args.list_pending:
        pending = list_pending_approvals(base_dir=base_dir)
        if not pending:
            print(json.dumps({"ok": True, "pending": []}, indent=2))
            return 0
        for item in pending:
            print(
                json.dumps(
                    _cli_payload(
                        ok=True,
                        status=STATUS_APPROVAL_REQUIRED,
                        candidate_id=item.candidate_id,
                        paper_submit_allowed=False,
                    ),
                    indent=2,
                )
            )
        return 0

    if not args.candidate_id or not args.decision:
        print("candidate_id and --decision required unless --list-pending", flush=True)
        return 1

    try:
        item = apply_operator_decision(
            args.candidate_id,
            args.decision,
            args.reason,
            base_dir=base_dir,
        )
    except FileNotFoundError:
        print(json.dumps({"ok": False, "error": "pending_approval_not_found"}, indent=2))
        return 1

    if item.approval_status == STATUS_APPROVED_BY_OPERATOR:
        status = STATUS_APPROVED_BY_OPERATOR
        allowed = True
    elif item.approval_status == STATUS_REJECTED_BY_OPERATOR:
        status = STATUS_REJECTED_BY_OPERATOR
        allowed = False
    else:
        status = item.approval_status
        allowed = item.paper_submit_allowed()

    print(
        json.dumps(
            _cli_payload(
                ok=True,
                status=status,
                candidate_id=item.candidate_id,
                paper_submit_allowed=allowed,
            ),
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
