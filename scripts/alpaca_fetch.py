#!/usr/bin/env python3
"""Read-only Alpaca chain snapshot fetch wrapper (AGENT-SKILLS-C2).

No order transport. No --live. Credentials via env only (never printed).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from qops.backtest.alpaca_greeks_layer import (
    PaperLiveSymbolSpec,
    check_alpaca_market_data_credentials,
    greeks_candidates_to_dataframe,
    load_local_env,
    stage_greeks_paper_live,
    try_create_option_client,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only Alpaca chain fetch (admin skill)")
    parser.add_argument("--base-dir", default=".", type=Path)
    parser.add_argument(
        "--symbols",
        default=None,
        help="Comma-separated underlyings (required with --fetch; optional for --env-check)",
    )
    parser.add_argument("--dte-range", nargs=2, type=int, metavar=("MIN", "MAX"))
    parser.add_argument("--delta-filter", nargs=2, type=float, metavar=("LOW", "HIGH"))
    parser.add_argument("--fetch", action="store_true", help="Perform read-only chain fetch")
    parser.add_argument(
        "--env-check",
        action="store_true",
        help="Credential check only; exit 2 on auth/credential failure",
    )
    parser.add_argument("--output", type=Path, default=None, help="Write JSON snapshot rows")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    if args.fetch and not args.env_check and not args.symbols:
        parser.error("--symbols is required with --fetch")
    return args


def _quote_age_seconds(quote_ts: object) -> int | None:
    if quote_ts is None:
        return None
    try:
        if isinstance(quote_ts, (int, float)):
            ts = float(quote_ts)
            if ts > 1e12:
                ts /= 1000.0
            return max(0, int(datetime.now(tz=timezone.utc).timestamp() - ts))
        raw = str(quote_ts).replace("Z", "+00:00")
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0, int((datetime.now(tz=timezone.utc) - dt).total_seconds()))
    except (TypeError, ValueError, OSError):
        return None


def _apply_delta_filter(rows: list[dict], low: float, high: float) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        delta = row.get("delta")
        if delta is None:
            continue
        try:
            d = abs(float(delta))
        except (TypeError, ValueError):
            continue
        if low <= d <= high:
            out.append(row)
    return out


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    load_local_env()

    if args.env_check:
        check = check_alpaca_market_data_credentials()
        if not args.quiet:
            print(json.dumps({"credential_status": check.credential_status}))
        if check.credential_status != "READY":
            return 2
        return 0

    if not args.fetch:
        if not args.quiet:
            print("fetch_required: pass --fetch for read-only chain snapshot")
        return 1

    check = check_alpaca_market_data_credentials()
    if check.credential_status != "READY":
        if not args.quiet:
            print(json.dumps({"error": "credential_not_ready"}))
        return 2

    client, client_error = try_create_option_client()
    if client is None:
        if not args.quiet:
            print(json.dumps({"error": client_error or "client_unavailable"}))
        return 2

    dte_min = 0
    dte_max = 3
    if args.dte_range:
        dte_min, dte_max = args.dte_range
    if dte_min < 0 or dte_max < dte_min:
        print(json.dumps({"error": "invalid_dte_range"}))
        return 1

    symbols = [s.strip().upper() for s in str(args.symbols or "").split(",") if s.strip()]
    if not symbols:
        if not args.quiet:
            print(json.dumps({"error": "symbols_required"}))
        return 1
    specs = [
        PaperLiveSymbolSpec(
            symbol=sym,
            current_price=None,
            source_profile="alpaca_fetch_cli",
            has_spy_context=sym == "SPY",
            provenance="scripts/alpaca_fetch.py",
        )
        for sym in symbols
    ]
    candidates, _fetch_attempted, _diag, _plans = stage_greeks_paper_live(
        specs,
        symbol_source="cli_symbols",
        fetch=True,
        client=client,
        dte_min=dte_min,
        dte_max=dte_max,
        strike_buffer_pct=0.03,
        risk_free_rate=0.05,
        allow_bs_fallback=False,
        fallback_volatility_proxy=None,
        min_time_to_expiry_days=None,
        max_contracts_per_symbol=500,
    )
    df = greeks_candidates_to_dataframe(candidates)
    rows = df.to_dict(orient="records")
    for row in rows:
        row["quote_age_seconds"] = _quote_age_seconds(row.get("quote_timestamp"))

    if args.delta_filter:
        low, high = args.delta_filter
        rows = _apply_delta_filter(rows, low, high)

    payload = {
        "dte_min": dte_min,
        "dte_max": dte_max,
        "symbol_count": len(symbols),
        "contract_rows": len(rows),
        "rows": rows,
    }

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    elif not args.quiet:
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
