"""Tests for SpotGamma private PDF ingest path validation and extraction."""

from __future__ import annotations

from pathlib import Path

import pytest

from qops.advisory.spotgamma_pdf_ingest import (
    PRIVATE_PARSED_ROOT,
    PRIVATE_RAW_ROOT,
    PRIVATE_TEXT_ROOT,
    PdfExtractionResult,
    assert_private_output_path,
    assert_private_raw_pdf_path,
    extract_pdf_text,
    save_extracted_text,
    write_parsed_json,
)


def _make_text_pdf(path: Path, text: str) -> None:
    import fitz

    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=10)
    doc.save(path)
    doc.close()


def test_private_path_constants() -> None:
    assert PRIVATE_RAW_ROOT == Path("private/raw/spotgamma")
    assert PRIVATE_TEXT_ROOT == Path("private/text/spotgamma")
    assert PRIVATE_PARSED_ROOT == Path("private/parsed/spotgamma")


def test_raw_pdf_path_must_be_under_private_raw(tmp_path: Path) -> None:
    bad = tmp_path / "data" / "founders_note.pdf"
    bad.parent.mkdir(parents=True)
    bad.write_bytes(b"%PDF-1.4")
    with pytest.raises(ValueError, match="private/raw/spotgamma"):
        assert_private_raw_pdf_path(bad, base_dir=tmp_path)

    good = tmp_path / "private" / "raw" / "spotgamma" / "founders_note_2026_07_09.pdf"
    good.parent.mkdir(parents=True)
    good.write_bytes(b"%PDF-1.4")
    assert assert_private_raw_pdf_path(good, base_dir=tmp_path) == good.resolve()


def test_output_path_must_be_under_private_parsed(tmp_path: Path) -> None:
    bad = tmp_path / "data" / "parsed" / "founders_note.json"
    with pytest.raises(ValueError, match="private/parsed/spotgamma"):
        assert_private_output_path(bad, base_dir=tmp_path)

    good = tmp_path / "private" / "parsed" / "spotgamma" / "founders_note_2026_07_09.json"
    assert assert_private_output_path(good, base_dir=tmp_path) == good.resolve()


def test_extract_pdf_text_from_synthetic_pdf(tmp_path: Path) -> None:
    fixture = Path(__file__).parent / "fixtures" / "sg_pdf_samples" / "founders_note_sample.txt"
    text = fixture.read_text(encoding="utf-8")
    pdf_path = tmp_path / "private" / "raw" / "spotgamma" / "founders_note_2026_07_09.pdf"
    _make_text_pdf(pdf_path, text)

    result = extract_pdf_text(pdf_path, base_dir=tmp_path)
    assert isinstance(result, PdfExtractionResult)
    assert result.status == "EXTRACTED"
    assert "Call Wall" in result.text
    assert result.page_count >= 1


def test_extract_pdf_text_empty_returns_needs_review(tmp_path: Path) -> None:
    import fitz

    pdf_path = tmp_path / "private" / "raw" / "spotgamma" / "empty.pdf"
    pdf_path.parent.mkdir(parents=True)
    doc = fitz.open()
    doc.new_page()
    doc.save(pdf_path)
    doc.close()

    result = extract_pdf_text(pdf_path, base_dir=tmp_path)
    assert result.status == "NEEDS_REVIEW"
    assert not result.text.strip()


def test_save_extracted_text_writes_private_text(tmp_path: Path) -> None:
    out = save_extracted_text(
        "sample text",
        stem="founders_note_2026_07_09",
        base_dir=tmp_path,
    )
    assert out.parent == (tmp_path / PRIVATE_TEXT_ROOT).resolve()
    assert out.read_text(encoding="utf-8") == "sample text"


def test_write_parsed_json_marks_proprietary(tmp_path: Path) -> None:
    out = tmp_path / "private" / "parsed" / "spotgamma" / "founders_note_2026_07_09.json"
    payload = {"report_date": "2026-07-09", "call_wall": 6300.0}
    write_parsed_json(payload, out, base_dir=tmp_path)
    import json

    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["proprietary"] is True
    assert data["private"] is True
    assert data["call_wall"] == 6300.0
