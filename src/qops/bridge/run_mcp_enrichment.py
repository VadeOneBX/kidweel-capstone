from __future__ import annotations

import argparse
from pathlib import Path

from qops.bridge.export import export_enriched_chatgpt_payloads
from qops.bridge.mcp_enrichment import enrich_chatgpt_payloads, load_chatgpt_payload_json


def main() -> None:
    """CLI: load C13D JSON, merge delayed-chain CSV snapshots, export enriched JSON."""
    parser = argparse.ArgumentParser(
        description="Fill chain_context on ChatGPT payloads from local MCP-fed chain CSVs."
    )
    parser.add_argument(
        "--payload",
        type=Path,
        required=True,
        help="Path to chatgpt_payload_*.json from C13D.",
    )
    parser.add_argument(
        "--chain-dir",
        type=Path,
        required=True,
        help="Directory containing one CSV per symbol: {symbol}.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/spotgamma/processed"),
        help="Output directory for chatgpt_payload_enriched_*.json",
    )
    args = parser.parse_args()

    payloads = load_chatgpt_payload_json(args.payload)
    enriched, stats = enrich_chatgpt_payloads(payloads, chain_dir=args.chain_dir)
    out_path = export_enriched_chatgpt_payloads(enriched, output_dir=args.output_dir)

    print(f"payload_count={stats.payload_count}")
    print(f"symbols_enriched={stats.enriched_count}")
    print(f"symbols_skipped={stats.skipped_count}")
    print(f"output_path={out_path}")


if __name__ == "__main__":
    main()
