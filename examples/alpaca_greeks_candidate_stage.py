#!/usr/bin/env python3
"""Stage Alpaca-first greeks rows for narrowed blueprint plans (ALPACA-GREEKS-C1).

Run:
  PYTHONPATH=src python examples/alpaca_greeks_candidate_stage.py --rebuild-if-missing --no-write --limit 10
  PYTHONPATH=src python examples/alpaca_greeks_candidate_stage.py --paper-live --symbols AAPL,AMD --no-write
  PYTHONPATH=src python examples/alpaca_greeks_candidate_stage.py --env-check
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from qops.backtest.alpaca_greeks_layer import (
    PAPER_LIVE_MODE,
    check_alpaca_market_data_credentials,
    fetch_diagnostics_summary,
    greeks_candidates_to_dataframe,
    load_blueprint_request_plans,
    load_local_env,
    resolve_paper_live_symbol_specs,
    sanitize_blueprint_descriptor,
    stage_greeks_for_plans,
    stage_greeks_paper_live,
    summarize_greeks_staging,
    try_create_option_client,
)


def _print_staging_summary(
    *,
    ns: argparse.Namespace,
    mode: str,
    plan_source: str,
    plans_count: int,
    plans_sample: list,
    candidates: list,
    fetch_attempted: bool,
    fetch_diag,
    client_error: str | None,
    summary: dict,
    symbols_requested: list[str] | None = None,
) -> None:
    print("Alpaca greeks candidate staging (no approval, no execution)")
    print("============================================================")
    print(f"mode: {mode}")
    print(f"blueprint_plan_source: {plan_source}")
    print(f"blueprint_input_rows: {summary['blueprint_input_rows']}")
    if plans_sample:
        print("blueprint_rows_sample (first 3, sanitized):")
        print(json.dumps(plans_sample, indent=2))
    print(f"greeks_candidate_rows: {summary['greeks_candidate_rows']}")
    print(f"fetch_requested: {ns.fetch}")
    print(f"fetch_attempted: {summary['fetch_attempted']}")
    if fetch_diag is not None:
        diag_summary = fetch_diagnostics_summary(fetch_diag)
        if fetch_diag.symbols_requested:
            print(f"symbols_requested: {list(fetch_diag.symbols_requested)}")
        elif symbols_requested:
            print(f"symbols_requested: {symbols_requested}")
        if fetch_diag.symbol_source:
            print(f"symbol_source: {fetch_diag.symbol_source}")
        print(f"fetch_requests_attempted: {diag_summary['requests_attempted']}")
        print(f"fetch_requests_empty: {diag_summary['requests_empty']}")
        print(f"fetch_requests_error: {diag_summary['requests_error']}")
        print(f"fetch_requests_invalid: {diag_summary['requests_invalid']}")
        print(f"contracts_before_filter: {diag_summary['contracts_before_filter']}")
        print(f"contracts_removed_by_dte_filter: {diag_summary['contracts_removed_by_dte_filter']}")
        print(f"contracts_removed_by_strike_filter: {diag_summary['contracts_removed_by_strike_filter']}")
        print(f"contracts_removed_by_filter: {diag_summary['contracts_removed_by_filter']}")
        print(f"contracts_after_filter: {diag_summary['contracts_after_filter']}")
        print(f"contracts_staged: {diag_summary['contracts_staged']}")
        if fetch_diag.failure_class:
            print(f"fetch_failure_class: {fetch_diag.failure_class}")
        if ns.debug_requests:
            print("fetch_request_descriptors_sample:")
            print(json.dumps(diag_summary["request_descriptors_sample"], indent=2))
            if diag_summary["empty_response_reasons_sample"]:
                print("fetch_empty_response_reasons_sample:")
                print(json.dumps(diag_summary["empty_response_reasons_sample"], indent=2))
            if diag_summary["error_summaries_sample"]:
                print("fetch_error_summaries_sample:")
                print(json.dumps(diag_summary["error_summaries_sample"], indent=2))
    elif symbols_requested:
        print(f"symbols_requested: {symbols_requested}")
    print(f"output_target: {ns.output.resolve()}")
    if client_error:
        print(f"fetch_client: skipped ({client_error})")
    print("greeks_source_counts:")
    print(json.dumps(summary["greeks_source_counts"], indent=2))
    print("greeks_status_counts:")
    print(json.dumps(summary["greeks_status_counts"], indent=2))
    print(f"missing_or_invalid_count: {summary['missing_or_invalid_count']}")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Alpaca greeks staging for blueprint-narrowed candidates")
    p.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/alpaca_blueprint_replay_plan.csv"),
    )
    p.add_argument(
        "--availability",
        type=Path,
        default=Path("data/processed/alpaca_replay_input_plan.csv"),
    )
    p.add_argument(
        "--candidates",
        type=Path,
        default=Path("data/processed/spotgamma_replay_candidates.csv"),
    )
    p.add_argument(
        "--context",
        type=Path,
        default=Path("data/processed/spotgamma_context_sample.csv"),
        help="SpotGamma context CSV for paper-live symbol corpus freshness",
    )
    p.add_argument("--spotgamma-root", type=Path, default=Path("data/spotgamma"))
    p.add_argument("--rebuild-if-missing", action="store_true")
    p.add_argument(
        "--paper-live",
        action="store_true",
        help="Use current trade date and DTE window (not replay blueprint expirations)",
    )
    p.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="Comma-separated underlyings for paper-live mode",
    )
    p.add_argument("--max-symbols", type=int, default=10)
    p.add_argument("--max-contracts-per-symbol", type=int, default=None)
    p.add_argument("--no-write", action="store_true")
    p.add_argument("--fetch", action="store_true", help="Read-only Alpaca option chain snapshot fetch")
    p.add_argument(
        "--env-check",
        action="store_true",
        help="Print credential_status only (loads .env when dotenv available); no fetch",
    )
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--dte-min", type=int, default=0)
    p.add_argument("--dte-max", type=int, default=None)
    p.add_argument("--strike-buffer-pct", type=float, default=0.03)
    p.add_argument("--risk-free-rate", type=float, default=0.05)
    p.add_argument(
        "--allow-bs-fallback",
        action="store_true",
        help="Compute BS/BSM greeks when Alpaca snapshot greeks are missing",
    )
    p.add_argument(
        "--fallback-volatility-proxy",
        type=float,
        default=None,
        help="Explicit IV proxy for BS fallback (marked on row); not used without --allow-bs-fallback",
    )
    p.add_argument(
        "--min-time-to-expiry-days",
        type=float,
        default=None,
        help="Optional minimum T floor in days for BS (0DTE); omit to fail closed on T<=0",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/alpaca_greeks_candidates.csv"),
    )
    p.add_argument(
        "--debug-requests",
        action="store_true",
        help="Print sanitized fetch diagnostics (no secrets)",
    )
    p.add_argument(
        "--fail-on-empty-fetch",
        action="store_true",
        help="Exit non-zero when --fetch is set and no contract rows are staged",
    )
    ns = p.parse_args(argv)

    dte_max = ns.dte_max if ns.dte_max is not None else (14 if ns.paper_live else 7)

    if ns.env_check:
        load_local_env()
        check = check_alpaca_market_data_credentials()
        print("Alpaca market-data credential check (read-only greeks layer)")
        print("credential_status:", check.credential_status)
        if check.env_pair_label:
            print("env_pair_label:", check.env_pair_label)
        if check.detail:
            print("detail:", check.detail)
        raise SystemExit(0 if check.credential_status == "READY" else 1)

    client = None
    client_error: str | None = None
    symbols_requested: list[str] | None = None
    if ns.fetch:
        load_local_env()
        creds = check_alpaca_market_data_credentials()
        if creds.credential_status != "READY":
            detail = creds.detail or "missing_credentials"
            print("Alpaca greeks candidate staging (no approval, no execution)")
            print("============================================================")
            print("fetch_requested: True")
            print("fetch_attempted: False")
            print(f"credential_status: {creds.credential_status}")
            print(f"credential_error: {detail}")
            raise SystemExit(1)
        client, client_error = try_create_option_client()
        if client is None:
            print("Alpaca greeks candidate staging (no approval, no execution)")
            print("============================================================")
            print("fetch_requested: True")
            print("fetch_attempted: False")
            print(f"fetch_client: skipped ({client_error})")
            raise SystemExit(1)

    if ns.paper_live:
        specs, symbol_source = resolve_paper_live_symbol_specs(
            symbols_csv=ns.symbols,
            candidates_csv=ns.candidates,
            context_csv=ns.context,
            spotgamma_root=ns.spotgamma_root,
            max_symbols=ns.max_symbols,
            limit=ns.limit,
        )
        candidates, fetch_attempted, fetch_diag, plans = stage_greeks_paper_live(
            specs,
            symbol_source=symbol_source,
            fetch=ns.fetch and client is not None,
            client=client,
            dte_min=ns.dte_min,
            dte_max=dte_max,
            strike_buffer_pct=ns.strike_buffer_pct,
            risk_free_rate=ns.risk_free_rate,
            allow_bs_fallback=ns.allow_bs_fallback,
            fallback_volatility_proxy=ns.fallback_volatility_proxy,
            min_time_to_expiry_days=ns.min_time_to_expiry_days,
            max_contracts_per_symbol=ns.max_contracts_per_symbol,
        )
        symbols_requested = [s.symbol for s in specs]
        plan_source = f"paper_live|{symbol_source}"
        mode = PAPER_LIVE_MODE
    else:
        plans, plan_source = load_blueprint_request_plans(
            input_csv=ns.input,
            availability_csv=ns.availability,
            candidates_csv=ns.candidates,
            spotgamma_root=ns.spotgamma_root,
            rebuild_if_missing=ns.rebuild_if_missing,
            dte_min=ns.dte_min,
            dte_max=dte_max,
            strike_buffer_pct=ns.strike_buffer_pct,
            limit=ns.limit,
        )
        candidates, fetch_attempted, fetch_diag = stage_greeks_for_plans(
            plans,
            fetch=ns.fetch and client is not None,
            client=client,
            risk_free_rate=ns.risk_free_rate,
            allow_bs_fallback=ns.allow_bs_fallback,
            fallback_volatility_proxy=ns.fallback_volatility_proxy,
            min_time_to_expiry_days=ns.min_time_to_expiry_days,
        )
        mode = "historical_replay"

    summary = summarize_greeks_staging(len(plans), candidates, fetch_attempted=fetch_attempted)
    plans_sample = [sanitize_blueprint_descriptor(p) for p in plans[:3]]

    _print_staging_summary(
        ns=ns,
        mode=mode,
        plan_source=plan_source,
        plans_count=len(plans),
        plans_sample=plans_sample,
        candidates=candidates,
        fetch_attempted=fetch_attempted,
        fetch_diag=fetch_diag,
        client_error=client_error,
        summary=summary,
        symbols_requested=symbols_requested,
    )

    if not ns.no_write and candidates:
        ns.output.parent.mkdir(parents=True, exist_ok=True)
        greeks_candidates_to_dataframe(candidates).to_csv(ns.output, index=False)
        print(f"wrote: {ns.output.resolve()} ({len(candidates)} rows)")
    elif ns.no_write:
        print("write: skipped (--no-write)")

    if ns.fail_on_empty_fetch and ns.fetch and fetch_attempted and not candidates:
        reason = fetch_diag.failure_class if fetch_diag and fetch_diag.failure_class else "EMPTY_FETCH_RESULT"
        print(f"fail_on_empty_fetch: {reason}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
