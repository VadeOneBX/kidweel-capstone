"""Deterministic local PDF text extraction for private vendor artifacts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

PRIVATE_RAW_ROOT = Path("private/raw")
PRIVATE_TEXT_ROOT = Path("private/text")
PRIVATE_PARSED_ROOT = Path("private/parsed")

PdfExtractionStatus = Literal["EXTRACTED", "NEEDS_REVIEW"]


@dataclass(frozen=True, slots=True)
class PdfExtractionResult:
    status: PdfExtractionStatus
    text: str
    page_count: int
    char_count: int


def _resolve_under(base_dir: Path, path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (base_dir / path).resolve()


def assert_private_raw_pdf_path(path: Path, *, base_dir: Path = Path(".")) -> Path:
    resolved = _resolve_under(base_dir, path)
    expected_root = (base_dir / PRIVATE_RAW_ROOT).resolve()
    if expected_root not in resolved.parents and resolved.parent != expected_root:
        raise ValueError(f"raw PDF path must be under {PRIVATE_RAW_ROOT}/: {path}")
    if resolved.suffix.lower() != ".pdf":
        raise ValueError(f"expected PDF file: {path}")
    return resolved


def assert_private_output_path(path: Path, *, base_dir: Path = Path(".")) -> Path:
    resolved = _resolve_under(base_dir, path)
    expected_root = (base_dir / PRIVATE_PARSED_ROOT).resolve()
    if expected_root not in resolved.parents and resolved.parent != expected_root:
        raise ValueError(f"parser output path must be under {PRIVATE_PARSED_ROOT}/: {path}")
    if resolved.suffix.lower() != ".json":
        raise ValueError(f"expected JSON output file: {path}")
    return resolved


def extract_pdf_text(path: Path, *, base_dir: Path = Path(".")) -> PdfExtractionResult:
    """Extract embedded text from a PDF using PyMuPDF (no OCR)."""
    pdf_path = assert_private_raw_pdf_path(path, base_dir=base_dir)
    if not pdf_path.is_file():
        raise FileNotFoundError(pdf_path)

    import fitz

    doc = fitz.open(pdf_path)
    try:
        parts: list[str] = []
        for page in doc:
            parts.append(page.get_text("text"))
        text = "\n".join(parts)
        page_count = doc.page_count
    finally:
        doc.close()

    cleaned = re.sub(r"\s+\n", "\n", text).strip()
    if not cleaned:
        return PdfExtractionResult(
            status="NEEDS_REVIEW",
            text="",
            page_count=page_count,
            char_count=0,
        )
    return PdfExtractionResult(
        status="EXTRACTED",
        text=cleaned,
        page_count=page_count,
        char_count=len(cleaned),
    )


def save_extracted_text(
    text: str,
    *,
    stem: str,
    base_dir: Path = Path("."),
) -> Path:
    out_dir = (base_dir / PRIVATE_TEXT_ROOT).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{stem}.txt"
    out_path.write_text(text, encoding="utf-8")
    return out_path


def write_parsed_json(
    payload: dict[str, object],
    out_path: Path,
    *,
    base_dir: Path = Path("."),
) -> Path:
    resolved = assert_private_output_path(out_path, base_dir=base_dir)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    enriched = {
        **payload,
        "proprietary": True,
        "private": True,
    }
    resolved.write_text(json.dumps(enriched, indent=2), encoding="utf-8")
    return resolved


def stem_from_pdf_path(pdf_path: Path) -> str:
    return pdf_path.stem
