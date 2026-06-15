#!/usr/bin/env python3
"""Dry-run or explicit paper submit for PAPER_PAYLOAD_READY rows (MCP-C12A)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from qops.execution.alpaca_paper_bridge import (
    CANONICAL_PAPER_BASE_URL,
    AuthMode,
    build_alpaca_mleg_order_request,
    check_alpaca_paper_credentials,
    check_alpaca_profile_cli_credentials,
    effective_transport_limit,
    filter_ready_payloads,
    load_local_env,
    load_paper_payload_rows,
    paper_transport_to_dataframe,
    profile_cli_submit_blocked,
    run_paper_payload_transport,
    sanitize_alpaca_mleg_order_request,
    summarize_paper_transport,
)


def _format_base_url_for_display(base_url: str | None) -> str:
    if not base_url or not str(base_url).strip():
        return "no"
    return base_url


def _print_env_triplet_check(*, require_paper_endpoint: bool) -> int:
    load_local_env()
    check = check_alpaca_paper_credentials(require_paper_endpoint=require_paper_endpoint)
    print("Alpaca paper transport env check (MCP-C12A)")
    print("===========================================")
    print("auth_mode: env_triplet")
    print(f"credential_status: {check.credential_status}")
    print(f"env_pair_label: {check.env_pair_label}")
    print(f"base_url: {_format_base_url_for_display(check.base_url)}")
    print(f"endpoint_ok: {check.endpoint_ok}")
    print(f"endpoint_detail: {check.endpoint_detail}")
    print(f"missing_keys: {list(check.missing_keys)}")
    print(f"canonical_paper_url: {CANONICAL_PAPER_BASE_URL}")
    if check.detail:
        print(f"detail: {check.detail}")
    if check.credential_status != "READY" or not check.endpoint_ok:
        return 1
    return 0


def _print_profile_cli_check() -> int:
    check = check_alpaca_profile_cli_credentials()
    print("Alpaca paper transport env check (MCP-C12A-AUTH2)")
    print("================================================")
    print("auth_mode: profile_cli")
    print(f"credential_status: {check.credential_status}")
    print(f"cli_argv: {' '.join(check.cli_argv)}")
    print(f"account_check_argv: {' '.join(check.account_check_argv)}")
    print(f"config_dir_source: {check.config_dir_source}")
    print(f"profile_source: {check.profile_source}")
    print(f"live_env_status: {check.live_env_status}")
    if check.detail:
        print(f"detail: {check.detail}")
    if check.credential_status != "READY_PROFILE_AUTH_PAPER_DEFAULT":
        return 1
    return 0


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Alpaca paper transport for payload candidates")
    p.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/paper_payload_candidates.csv"),
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/paper_transport_results.csv"),
    )
    p.add_argument("--no-write", action="store_true")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--env-check", action="store_true")
    p.add_argument(
        "--auth-mode",
        choices=("env_triplet", "profile_cli"),
        default="env_triplet",
        help="env_triplet: ALPACA_PAPER_* vars; profile_cli: Alpaca CLI profile check (env-check only)",
    )
    p.add_argument(
        "--submit-paper",
        action="store_true",
        help="Submit to Alpaca paper (default is dry-run only)",
    )
    p.add_argument(
        "--require-paper-endpoint",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    p.add_argument(
        "--print-request-json",
        action="store_true",
        help="Print sanitized Alpaca mleg order JSON for ready rows (no secrets; no submit unless --submit-paper)",
    )
    ns = p.parse_args(argv)
    auth_mode: AuthMode = ns.auth_mode

    if ns.env_check:
        code = (
            _print_profile_cli_check()
            if auth_mode == "profile_cli"
            else _print_env_triplet_check(require_paper_endpoint=ns.require_paper_endpoint)
        )
        sys.exit(code)

    blocked = profile_cli_submit_blocked(auth_mode, submit_paper=ns.submit_paper)
    if blocked:
        print("Paper payload transport (MCP-C12A)")
        print("==================================")
        print(f"fatal_error: {blocked}")
        sys.exit(1)

    rows = load_paper_payload_rows(ns.input)
    if not rows:
        print("Paper payload transport (MCP-C12A)")
        print("==================================")
        print(f"input_payload_candidates: 0 ({ns.input} missing or empty)")
        print("note: run examples/build_paper_payload_candidates.py first")
        return

    limit = effective_transport_limit(submit_paper=ns.submit_paper, limit=ns.limit)
    if ns.print_request_json:
        ready_preview = filter_ready_payloads(rows)[:limit]
        for payload in ready_preview:
            request = build_alpaca_mleg_order_request(payload)
            print(
                json.dumps(
                    {
                        "payload_id": payload.payload_id,
                        "structure_type": payload.structure_type,
                        "broker_request": sanitize_alpaca_mleg_order_request(request),
                    },
                    sort_keys=True,
                )
            )

    results, fatal = run_paper_payload_transport(
        rows,
        submit_paper=ns.submit_paper,
        limit=limit,
        require_paper_endpoint=ns.require_paper_endpoint,
    )
    summary = summarize_paper_transport(rows, results)

    print("Paper payload transport (MCP-C12A)")
    print("==================================")
    print(f"auth_mode: {auth_mode}")
    print(f"input_payload_candidates: {summary['input_payload_candidates']}")
    print(f"paper_payload_ready_count: {summary['paper_payload_ready_count']}")
    print(f"dry_run_ready_count: {summary['dry_run_ready_count']}")
    print(f"paper_submitted_count: {summary['paper_submitted_count']}")
    print(f"submit_attempted: {ns.submit_paper}")
    print(f"transport_limit: {limit}")
    print(f"dry_run: {not ns.submit_paper}")

    if fatal:
        print(f"fatal_error: {fatal}")
        sys.exit(1)

    for r in results:
        print(
            json.dumps(
                {
                    "payload_id": r.payload_id,
                    "symbol": r.symbol,
                    "structure_type": r.structure_type,
                    "transport_status": r.transport_status,
                    "dry_run": r.dry_run,
                    "message": r.message,
                }
            )
        )

    if not ns.no_write and results:
        ns.output.parent.mkdir(parents=True, exist_ok=True)
        paper_transport_to_dataframe(results).to_csv(ns.output, index=False)
        print(f"wrote: {ns.output.resolve()}")
    elif ns.no_write:
        print("write: skipped (--no-write)")


if __name__ == "__main__":
    main()
