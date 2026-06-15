#!/usr/bin/env python3
"""Read-only paper position audit after filled mleg orders (POSITION-C1)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from qops.execution.paper_position_audit import (
    DEFAULT_TRANSPORT_RESULTS_PATH,
    load_filled_order_audit_inputs,
    paper_position_audit_to_dataframe,
    resolve_filled_order_input_path,
    run_paper_position_audit,
    summarize_paper_position_audit,
)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Read-only Alpaca paper position audit")
    p.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/paper_order_status_audit.csv"),
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/paper_position_audit.csv"),
    )
    p.add_argument("--limit", type=int, default=1)
    p.add_argument("--no-write", action="store_true")
    p.add_argument(
        "--require-paper-endpoint",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    ns = p.parse_args(argv)

    source, resolved = resolve_filled_order_input_path(ns.input)
    rows, _ = load_filled_order_audit_inputs(ns.input)
    summary = summarize_paper_position_audit(rows, [])

    print("Paper position audit (POSITION-C1)")
    print("================================")
    print(f"input_source: {source}")
    print(f"input_path: {resolved.resolve()}")
    if source == "transport" and ns.input != resolved:
        print(f"note: status audit missing; using {DEFAULT_TRANSPORT_RESULTS_PATH}")

    print(f"filled_orders_found: {summary['filled_orders_found']}")

    if summary["filled_orders_found"] == 0:
        print("position_checks_attempted: 0")
        if source == "status_audit":
            print("note: no rows with current_status=filled in status audit input")
        else:
            print("note: no PAPER_SUBMITTED rows with external_order_id in transport input")
        return

    audits, fatal = run_paper_position_audit(
        rows,
        limit=ns.limit,
        require_paper_endpoint=ns.require_paper_endpoint,
    )
    summary = summarize_paper_position_audit(rows, audits)
    print(f"position_checks_attempted: {summary['position_checks_attempted']}")
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
                    "symbol": audit.symbol,
                    "structure_type": audit.structure_type,
                    "expected_long_leg_symbol": audit.expected_long_leg_symbol,
                    "expected_short_leg_symbol": audit.expected_short_leg_symbol,
                    "long_leg_position_found": audit.long_leg_position_found,
                    "short_leg_position_found": audit.short_leg_position_found,
                    "position_status": audit.position_status,
                    "failure_reasons": audit.failure_reasons,
                }
            )
        )

    if not ns.no_write and audits:
        ns.output.parent.mkdir(parents=True, exist_ok=True)
        paper_position_audit_to_dataframe(audits).to_csv(ns.output, index=False)
        print(f"wrote: {ns.output.resolve()}")
    elif ns.no_write:
        print("write: skipped (--no-write)")


if __name__ == "__main__":
    main()
