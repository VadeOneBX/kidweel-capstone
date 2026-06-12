#!/usr/bin/env python3
"""Read-only post-submit paper order status audit (MCP-C12A-POST1)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from qops.execution.paper_order_status import (
    load_paper_transport_results,
    paper_order_status_audit_to_dataframe,
    run_paper_order_status_audit,
    summarize_paper_order_status_audit,
)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Read-only Alpaca paper order status audit")
    p.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/paper_transport_results.csv"),
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/paper_order_status_audit.csv"),
    )
    p.add_argument("--limit", type=int, default=1)
    p.add_argument("--no-write", action="store_true")
    p.add_argument(
        "--require-paper-endpoint",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    ns = p.parse_args(argv)

    rows = load_paper_transport_results(ns.input)
    summary = summarize_paper_order_status_audit(rows, [])

    print("Paper order status audit (MCP-C12A-POST1)")
    print("=========================================")
    print(f"input_transport_rows: {summary['input_transport_rows']}")
    print(f"submitted_orders_found: {summary['submitted_orders_found']}")

    if summary["submitted_orders_found"] == 0:
        print("status_checks_attempted: 0")
        print("note: no PAPER_SUBMITTED rows with external_order_id")
        return

    audits, fatal = run_paper_order_status_audit(
        rows,
        limit=ns.limit,
        require_paper_endpoint=ns.require_paper_endpoint,
    )
    summary = summarize_paper_order_status_audit(rows, audits)
    print(f"status_checks_attempted: {summary['status_checks_attempted']}")
    print(f"audit_limit: {ns.limit}")

    if fatal:
        print(f"fatal_error: {fatal}")
        sys.exit(1)

    for audit in audits:
        print(
            json.dumps(
                {
                    "payload_id": audit.payload_id,
                    "external_order_id": audit.external_order_id,
                    "previous_status": audit.previous_status,
                    "current_status": audit.current_status,
                    "filled_qty": audit.filled_qty,
                    "filled_avg_price": audit.filled_avg_price,
                    "failure_reasons": audit.failure_reasons,
                }
            )
        )

    if not ns.no_write and audits:
        ns.output.parent.mkdir(parents=True, exist_ok=True)
        paper_order_status_audit_to_dataframe(audits).to_csv(ns.output, index=False)
        print(f"wrote: {ns.output.resolve()}")
    elif ns.no_write:
        print("write: skipped (--no-write)")


if __name__ == "__main__":
    main()
