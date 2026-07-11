#!/usr/bin/env python3
"""CLI for private vendor PDF ingest."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from qops.advisory.private_flow_report_parser import parse_flow_report_text
from qops.advisory.private_macro_note_parser import parse_macro_note_text
from qops.advisory.private_vendor_pdf_ingest import (
    extract_pdf_text,
    save_extracted_text,
    stem_from_pdf_path,
    write_parsed_json,
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Parse private vendor PDF artifacts.",
        epilog=(
            "Exit codes: 0=success (Wrote private/parsed/<stem>.json); "
            "2=NEEDS_REVIEW (JSON still written; no extractable text; no OCR). "
            "Other nonzero=unexpected failure."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--kind",
        required=True,
        choices=("macro_note", "flow_report"),
        help="Private artifact kind",
    )
    parser.add_argument("--pdf", required=True, type=Path, help="Path to private raw PDF")
    parser.add_argument("--out", required=True, type=Path, help="Path to private parsed JSON output")
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path("."),
        help="Repository base directory (default: cwd)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    base_dir = args.base_dir.resolve()

    extraction = extract_pdf_text(args.pdf, base_dir=base_dir)
    stem = stem_from_pdf_path(args.pdf)
    if extraction.text:
        save_extracted_text(extraction.text, stem=stem, base_dir=base_dir)

    if extraction.status == "NEEDS_REVIEW":
        payload: dict[str, object] = {
            "kind": args.kind,
            "parse_status": "NEEDS_REVIEW",
            "parse_confidence": "LOW",
            "report_date": "",
        }
        write_parsed_json(payload, args.out, base_dir=base_dir)
        print(f"NEEDS_REVIEW: no extractable text in {args.pdf}", file=sys.stderr)
        return 2

    if args.kind == "macro_note":
        payload = parse_macro_note_text(extraction.text)
    else:
        payload = parse_flow_report_text(extraction.text)

    out_path = write_parsed_json(payload, args.out, base_dir=base_dir)
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
