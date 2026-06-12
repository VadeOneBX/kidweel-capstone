#!/usr/bin/env python3
"""Controlled paper mleg closeout (CLOSE-C1). Default dry-run; --close-paper is explicit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from qops.execution.alpaca_paper_bridge import sanitize_alpaca_mleg_order_request
from qops.execution.alpaca_paper_bridge import load_paper_payload_rows
from qops.execution.paper_closeout import (
    QUOTE_BASED_CLOSE_PRICE_IMPLEMENTED,
    build_alpaca_close_mleg_order_request,
    filled_order_audit_input_for_close,
    filter_filled_order_status_rows,
    load_paper_order_status_audit_rows,
    paper_closeout_to_dataframe,
    resolve_close_client_order_attempt,
    resolve_spread_close_pricing,
    run_paper_closeout,
    summarize_paper_closeout,
)
from qops.execution.spread_close_pricing import OptionLegQuote, leg_quote_to_dict
from qops.execution.paper_position_audit import audit_one_filled_order, get_alpaca_paper_positions


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Controlled Alpaca paper mleg closeout")
    p.add_argument("--payload-id", type=str, default=None)
    p.add_argument(
        "--input-status",
        type=Path,
        default=Path("data/processed/paper_order_status_audit.csv"),
    )
    p.add_argument(
        "--input-payloads",
        type=Path,
        default=Path("data/processed/paper_payload_candidates.csv"),
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/paper_closeout_results.csv"),
    )
    p.add_argument("--limit", type=int, default=1)
    p.add_argument("--no-write", action="store_true")
    p.add_argument("--print-request-json", action="store_true")
    p.add_argument(
        "--close-paper",
        action="store_true",
        help="Submit close order to Alpaca paper (default is dry-run only)",
    )
    p.add_argument("--limit-price", type=float, default=None)
    p.add_argument(
        "--price-source",
        choices=("quote_mid",),
        default="quote_mid",
        help="Close limit from live option quote mids (default)",
    )
    p.add_argument(
        "--close-attempt",
        type=int,
        default=None,
        help="Close client_order_id attempt suffix (default: prior closeout rows + 1)",
    )
    p.add_argument(
        "--require-paper-endpoint",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    ns = p.parse_args(argv)

    status_rows = load_paper_order_status_audit_rows(ns.input_status)
    payload_rows = load_paper_payload_rows(ns.input_payloads)
    summary = summarize_paper_closeout(
        status_rows,
        payload_rows,
        [],
        payload_id=ns.payload_id,
    )

    print("Paper closeout (CLOSE-C1)")
    print("=========================")
    print(f"filled_orders_found: {summary['filled_orders_found']}")
    print(f"payload_rows_matched: {summary['payload_rows_matched']}")
    print(f"quote_based_close_price_implemented: {QUOTE_BASED_CLOSE_PRICE_IMPLEMENTED}")
    print(f"price_source: {ns.price_source}")
    print("explicit_limit_price_override: optional via --limit-price")
    print(f"close_paper: {ns.close_paper}")
    print(f"dry_run: {not ns.close_paper}")

    if summary["filled_orders_found"] == 0:
        print("note: no filled order status rows matched filters")
        return

    filled = filter_filled_order_status_rows(status_rows, payload_id=ns.payload_id)
    if ns.limit is not None and ns.limit >= 0:
        filled = filled[: ns.limit]

    position_verification = "not_run"
    if filled and payload_rows:
        payloads = {row.payload_id: row for row in payload_rows if row.payload_id}
        status_row = filled[0]
        payload = payloads.get(status_row.payload_id)
        if payload is not None:
            from qops.execution.alpaca_paper_bridge import resolve_alpaca_paper_credentials

            creds = resolve_alpaca_paper_credentials(
                require_paper_endpoint=ns.require_paper_endpoint
            )
            if creds is not None:
                pos_raw = get_alpaca_paper_positions(creds)
                snapshots = pos_raw.get("positions")
                if not isinstance(snapshots, list):
                    snapshots = []
                index = {s.symbol: s for s in snapshots if s.symbol}
                audit = audit_one_filled_order(
                    filled_order_audit_input_for_close(status_row, payload),
                    index,
                    fetch_ok=bool(pos_raw.get("ok")),
                    fetch_failure=str(pos_raw.get("failure_reasons") or ""),
                )
                position_verification = audit.position_status
    print(f"position_verification: {position_verification}")

    quote_fetch_attempted = False
    pricing_preview = None
    if filled and payload_rows:
        payloads = {row.payload_id: row for row in payload_rows if row.payload_id}
        status_row = filled[0]
        payload = payloads.get(status_row.payload_id)
        if payload is not None:
            pricing_preview = resolve_spread_close_pricing(
                payload,
                price_source=ns.price_source,
                explicit_limit_price=ns.limit_price,
            )
            quote_fetch_attempted = pricing_preview.quote_fetch_attempted
            print(f"quote_fetch_attempted: {quote_fetch_attempted}")
            print(
                json.dumps(
                    {
                        "long_leg_quote": leg_quote_to_dict(pricing_preview.long_leg),
                        "short_leg_quote": leg_quote_to_dict(pricing_preview.short_leg),
                        "spread_mid": pricing_preview.spread_mid,
                        "suggested_close_limit": pricing_preview.suggested_close_limit,
                        "close_price_source": pricing_preview.close_price_source,
                        "close_price_status": pricing_preview.close_price_status,
                    }
                )
            )

    results, fatal = run_paper_closeout(
        status_rows,
        payload_rows,
        payload_id=ns.payload_id,
        limit=ns.limit,
        close_paper=ns.close_paper,
        limit_price=ns.limit_price,
        price_source=ns.price_source,
        require_paper_endpoint=ns.require_paper_endpoint,
        close_results_path=ns.output,
        close_attempt=ns.close_attempt,
    )
    summary = summarize_paper_closeout(
        status_rows,
        payload_rows,
        results,
        payload_id=ns.payload_id,
    )
    print(f"close_results_count: {summary['close_results_count']}")
    print(f"dry_run_ready_count: {summary['dry_run_ready_count']}")

    if fatal:
        print(f"fatal_error: {fatal}")
        sys.exit(1)

    for result in results:
        print(
            json.dumps(
                {
                    "payload_id": result.payload_id,
                    "original_external_order_id": result.original_external_order_id,
                    "close_status": result.close_status,
                    "dry_run": result.dry_run,
                    "message": result.message,
                    "failure_reasons": result.failure_reasons,
                }
            )
        )

    if ns.print_request_json and filled:
        status_row = filled[0]
        payloads = {row.payload_id: row for row in payload_rows if row.payload_id}
        payload = payloads.get(status_row.payload_id)
        if payload is not None:
            pricing = pricing_preview or resolve_spread_close_pricing(
                payload,
                price_source=ns.price_source,
                explicit_limit_price=ns.limit_price,
            )
            resolved = pricing.suggested_close_limit
            if resolved is not None:
                attempt = resolve_close_client_order_attempt(
                    status_row.payload_id,
                    results_path=ns.output,
                    explicit_attempt=ns.close_attempt,
                )
                request = build_alpaca_close_mleg_order_request(
                    payload,
                    limit_price=resolved,
                    close_attempt=attempt,
                )
                print(
                    json.dumps(
                        {
                            "payload_id": status_row.payload_id,
                            "structure_type": payload.structure_type,
                            "close_price_source": pricing.close_price_source,
                            "close_price_status": pricing.close_price_status,
                            "spread_mid": pricing.spread_mid,
                            "suggested_close_limit": pricing.suggested_close_limit,
                            "close_client_order_attempt": attempt,
                            "broker_request": sanitize_alpaca_mleg_order_request(request),
                        },
                        sort_keys=True,
                    )
                )
            else:
                print(
                    json.dumps(
                        {
                            "payload_id": status_row.payload_id,
                            "close_price_status": pricing.close_price_status,
                            "close_price_source": pricing.close_price_source,
                            "broker_request": None,
                        }
                    )
                )

    if not ns.no_write and results:
        ns.output.parent.mkdir(parents=True, exist_ok=True)
        paper_closeout_to_dataframe(results).to_csv(ns.output, index=False)
        print(f"wrote: {ns.output.resolve()}")
    elif ns.no_write:
        print("write: skipped (--no-write)")


if __name__ == "__main__":
    main()
