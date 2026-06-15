from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from alpaca.common.exceptions import APIError
from alpaca.data.historical.option import OptionHistoricalDataClient

from qops.bridge.chain_snapshot_export import (
    chain_output_path,
    extract_unique_symbol_dates,
    fetch_chain_dataframe_for_symbol,
    read_payload_json,
    write_chain_snapshot_csv,
)
from qops.bridge.chain_snapshot_models import ChainSnapshotFetchSummary, summary_to_dict

# C13D payload shape is JSON exported from bridge/export.py.
# This script is independent from execution/risk logic: it only fetches delayed
# option-chain data and writes canonical local CSVs for later C13E enrichment.


def _safe_load_env() -> None:
    """Load ``.env`` from the current working directory. Permission errors are tolerated."""

    try:
        load_dotenv()
    except PermissionError:
        pass


def run_fetch(
    *,
    input_json: str | Path,
    output_root: str | Path,
    strikes_each_side: int = 10,
) -> ChainSnapshotFetchSummary:
    """Read C13D payload JSON, fetch delayed chain snapshots per unique pair, write CSVs.

    For each unique ``(trade_date, symbol)`` (spot from first-seen ``price``), writes::

        {output_root}/{trade_date}/{SYMBOL}.csv

    Skips gracefully when the API returns no contracts or the request fails (network,
    auth, rate limits). Raises on malformed tabular data that cannot be normalized or
    on filesystem write errors.

    Args:
        input_json: Path to C13D ``chatgpt_payload_*.json``.
        output_root: Root directory (e.g. ``data/options/chain_snapshots``).
        strikes_each_side: After fetch, retain only ±N strike steps around ATM per expiry.

    Returns:
        Counts and skipped underlying symbols (best-effort labels on failure).
    """
    _safe_load_env()
    payload = read_payload_json(input_json)
    pairs = extract_unique_symbol_dates(payload)

    try:
        client = OptionHistoricalDataClient(raw_data=True)
    except ValueError as exc:
        msg = str(exc).lower()
        if "authentication" in msg or "credential" in msg or "supply" in msg:
            return ChainSnapshotFetchSummary(
                requested=len(pairs),
                fetched=0,
                skipped=[sym for _, sym, _ in pairs],
                output_root=str(output_root),
            )
        raise

    requested = 0
    fetched = 0
    skipped: list[str] = []

    for trade_date, symbol, spot_price in pairs:
        requested += 1
        try:
            df_chain = fetch_chain_dataframe_for_symbol(
                client,
                symbol=symbol,
                trade_date=trade_date,
                spot_price=spot_price,
                strikes_each_side=strikes_each_side,
            )
        except (ValueError, OSError):
            raise
        except APIError:
            skipped.append(symbol)
            continue
        except Exception:
            skipped.append(symbol)
            continue

        if df_chain.empty:
            skipped.append(symbol)
            continue

        out_path = chain_output_path(output_root, trade_date, symbol)
        write_chain_snapshot_csv(df_chain, out_path)
        fetched += 1

    return ChainSnapshotFetchSummary(
        requested=requested,
        fetched=fetched,
        skipped=skipped,
        output_root=str(output_root),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch delayed options-chain snapshots for C13D ChatGPT payload symbols."
    )
    parser.add_argument(
        "--input-json",
        required=True,
        help="Path to C13D ChatGPT payload JSON (from bridge/export).",
    )
    parser.add_argument(
        "--output-root",
        default="data/options/chain_snapshots",
        help="Root directory for chain snapshot CSVs (default: data/options/chain_snapshots).",
    )
    parser.add_argument(
        "--strikes-each-side",
        type=int,
        default=10,
        metavar="N",
        help="Keep ±N strike rungs around ATM per expiration after fetch (default: 10).",
    )
    args = parser.parse_args()

    summary = run_fetch(
        input_json=args.input_json,
        output_root=args.output_root,
        strikes_each_side=args.strikes_each_side,
    )
    d = summary_to_dict(summary)

    print(f"requested={d['requested']}")
    print(f"fetched={d['fetched']}")
    print(f"skipped={len(d['skipped'])}")
    if d["skipped"]:
        print(f"skipped_symbols={','.join(d['skipped'])}")
    print(f"output_root={d['output_root']}")


if __name__ == "__main__":
    main()
