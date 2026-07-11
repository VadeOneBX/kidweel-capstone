"""Leak-prevention tests for private vendor PDF ingest."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from qops.advisory.private_context_builder import build_sanitized_advisory_context
from qops.advisory.private_vendor_pdf_ingest import (
    assert_private_output_path,
    assert_private_raw_pdf_path,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

_PROPRIETARY_MARKER = "SYNTHETIC_FIXTURE_ONLY_9CE2_PROPRIETARY"

_BANNED_PRODUCT_TERMS = (
    "flowpatrol",
    "flow patrol",
    "founder's note",
    "founders note",
    "founders_note",
    "founder note",
)

_BANNED_SECTION_TERMS = (
    "executive summary bullets",
    "statistically significant positions",
    "largest premium trades",
    "sector statistical analysis",
)

_LEGACY_PATH_PATTERN = re.compile(r"data/spotgamma[/\w.-]*", re.IGNORECASE)


def _strip_legacy_path_refs(content: str) -> str:
    return _LEGACY_PATH_PATTERN.sub("", content)


def _assert_no_banned_product_terms(content: str, *, context: str) -> None:
    lowered = content.lower()
    for term in _BANNED_PRODUCT_TERMS:
        assert term not in lowered, f"banned product term '{term}' in {context}"
    for term in _BANNED_SECTION_TERMS:
        assert term not in lowered, f"banned section inventory '{term}' in {context}"


def _assert_no_spotgamma_prose(content: str, *, context: str) -> None:
    check = _strip_legacy_path_refs(content)
    assert "spotgamma" not in check.lower(), f"vendor name 'spotgamma' in {context}"


def _module_docstring(path: Path) -> str:
    content = path.read_text(encoding="utf-8")
    parts = content.split('"""')
    return parts[1] if len(parts) >= 3 else ""


def test_gitignore_contains_generic_private_patterns() -> None:
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    required = [
        "private/",
        "data/raw/vendor/",
        "data/parsed/vendor/",
        "logs/vendor/",
        "**/*private*vendor*.pdf",
        "**/*private*vendor*.txt",
        "**/*private*vendor*.json",
    ]
    for pattern in required:
        assert pattern in gitignore, f"missing .gitignore pattern: {pattern}"


def test_docs_do_not_contain_vendor_product_names() -> None:
    docs_dir = REPO_ROOT / "docs"
    for path in docs_dir.rglob("*.md"):
        content = path.read_text(encoding="utf-8", errors="replace")
        _assert_no_banned_product_terms(content, context=str(path))
        assert _PROPRIETARY_MARKER not in content


def test_readme_does_not_contain_vendor_product_names() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    _assert_no_banned_product_terms(readme, context="README.md")
    _assert_no_spotgamma_prose(readme, context="README.md")
    assert _PROPRIETARY_MARKER not in readme


def test_operator_commands_private_section_is_generic() -> None:
    import re

    content = (REPO_ROOT / "docs" / "operator_commands.md").read_text(encoding="utf-8")
    match = re.search(
        r"(?ms)^## Private vendor PDF ingest\n(.*?)(?=^## |\Z)",
        content,
    )
    assert match is not None, "missing Private vendor PDF ingest section"
    section = match.group(1)
    _assert_no_banned_product_terms(section, context="operator_commands private section")
    _assert_no_spotgamma_prose(section, context="operator_commands private section")
    assert "private/raw/" in section
    assert "parse_private_vendor_pdf.py" in section


def test_sanitized_context_avoids_raw_prose_and_section_names() -> None:
    macro = {
        "proprietary": True,
        "private": True,
        "kind": "macro_note",
        "report_date": "2026-07-09",
        "macro_note_summary": (
            "A" * 400 + " proprietary paragraph that must not appear verbatim in brief output."
        ),
        "macro_theme": "Range-bound",
        "call_wall": 6300.0,
        "put_wall": 6150.0,
        "zero_gamma_level": 6225.0,
        "volatility_trigger": 6180.0,
        "implied_1d_move_pct": 0.85,
        "skew_commentary": "elevated",
        "risk_reversal_25d": -2.5,
        "index_levels": {"resistance": 6280.0, "support": 6180.0},
    }
    flow = {
        "proprietary": True,
        "private": True,
        "kind": "flow_report",
        "report_date": "2026-07-09",
        "overview_bullets": ["Index positioning skewed bullish on delta"],
        "top_symbols": ["AAPL", "NVDA"],
    }
    sanitized = build_sanitized_advisory_context(macro_note=macro, flow_report=flow)
    summary = sanitized["operator_safe_summary"]
    assert macro["macro_note_summary"] not in summary
    assert len(summary) < 500
    dumped = str(sanitized).lower()
    for term in _BANNED_SECTION_TERMS:
        assert term not in dumped
    assert "investment advice" not in summary.lower()


def test_parser_output_path_must_be_private_parsed(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        assert_private_output_path(tmp_path / "data" / "macro_note.json", base_dir=tmp_path)
    ok = tmp_path / "private" / "parsed" / "macro_note_2026_07_09.json"
    assert_private_output_path(ok, base_dir=tmp_path)


def test_raw_pdf_path_must_be_private_raw(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        assert_private_raw_pdf_path(tmp_path / "macro_note.pdf", base_dir=tmp_path)
    ok = tmp_path / "private" / "raw" / "macro_note_2026_07_09.pdf"
    ok.parent.mkdir(parents=True)
    ok.write_bytes(b"%PDF")
    assert_private_raw_pdf_path(ok, base_dir=tmp_path)


def test_no_private_artifacts_tracked_in_git() -> None:
    import subprocess

    result = subprocess.run(
        ["git", "ls-files", "private/"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    tracked = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    assert tracked == [], f"private artifacts tracked in git: {tracked}"


def test_sanitized_context_excludes_full_tables_and_paths() -> None:
    flow = {
        "proprietary": True,
        "private": True,
        "kind": "flow_report",
        "report_date": "2026-07-09",
        "directional_table": [{"symbol": "SPY", "delta_mm": 1200, "percentile": 88}],
        "top_symbols": ["SPY"],
        "overview_bullets": ["summary"],
    }
    sanitized = build_sanitized_advisory_context(flow_report=flow)
    dumped = str(sanitized)
    assert "directional_table" not in dumped
    assert "private/raw" not in dumped


def test_new_advisory_modules_avoid_vendor_names_in_docstrings() -> None:
    module_paths = [
        REPO_ROOT / "src/qops/advisory/private_vendor_pdf_ingest.py",
        REPO_ROOT / "src/qops/advisory/private_macro_note_parser.py",
        REPO_ROOT / "src/qops/advisory/private_flow_report_parser.py",
        REPO_ROOT / "src/qops/advisory/private_context_builder.py",
        REPO_ROOT / "scripts/parse_private_vendor_pdf.py",
    ]
    for path in module_paths:
        docstring = _module_docstring(path)
        _assert_no_banned_product_terms(docstring, context=f"{path} docstring")
        _assert_no_spotgamma_prose(docstring, context=f"{path} docstring")
