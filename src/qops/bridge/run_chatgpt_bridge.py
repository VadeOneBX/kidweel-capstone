from __future__ import annotations

import argparse
from pathlib import Path

from qops.bridge.export import export_chatgpt_payloads
from qops.bridge.payload_builder import build_chatgpt_payloads
from qops.bridge.spotgamma_loader import load_processed_spotgamma_csv
from qops.bridge.spy_context_loader import load_spy_context_csv


def main() -> None:
    """CLI entry: load SpotGamma CSV, optional SPY context, export JSON payloads."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--spy-context-csv", required=False, default=None)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    df = load_processed_spotgamma_csv(args.input_csv)
    spy_df = None
    if args.spy_context_csv:
        spy_path = Path(args.spy_context_csv)
        spy_df = load_spy_context_csv(spy_path)

    payloads = build_chatgpt_payloads(df, spy_df=spy_df)
    output_path = export_chatgpt_payloads(payloads, output_dir=args.output_dir)

    print(f"payloads={len(payloads)}")
    print(f"output={output_path}")


if __name__ == "__main__":
    main()
