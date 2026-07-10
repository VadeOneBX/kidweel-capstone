"""Leak-prevention tests for SpotGamma private PDF ingest."""

from __future__ import annotations

from pathlib import Path

import pytest

from qops.advisory.private_context_builder import build_sanitized_advisory_context
from qops.advisory.spotgamma_pdf_ingest import (
    assert_private_output_path,
    assert_private_raw_pdf_path,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

# Synthetic marker present only in test fixtures — must not appear in public docs.
_PROPRIETARY_MARKER = "SYNTHETIC_FIXTURE_ONLY_9CE2_PROPRIETARY"


def test_gitignore_contains_private_and_spotgamma_patterns() -> None:
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    required = [
        "private/",
        "**/*founder*note*.pdf",
        "**/*founder*note*.txt",
        "**/*flowpatrol*.pdf",
        "**/*flowpatrol*.txt",
        "**/*spotgamma*.pdf",
        "**/*spotgamma*.txt",
        "**/*spotgamma*.json",
        "data/raw/spotgamma/",
        "data/parsed/spotgamma/",
        "logs/spotgamma/",
    ]
    for pattern in required:
        assert pattern in gitignore, f"missing .gitignore pattern: {pattern}"


def test_docs_do_not_contain_fixture_proprietary_marker() -> None:
    docs_dir = REPO_ROOT / "docs"
    for path in docs_dir.rglob("*.md"):
        content = path.read_text(encoding="utf-8", errors="replace")
        assert _PROPRIETARY_MARKER not in content, f"leak in {path}"


def test_readme_does_not_mention_flowpatrol_contents() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    forbidden = [
        "FlowPatrol executive summary",
        "statistically significant positions table",
        "largest premium trades",
        _PROPRIETARY_MARKER,
    ]
    lowered = readme.lower()
    for phrase in forbidden:
        assert phrase.lower() not in lowered


def test_claude_brief_template_avoids_full_proprietary_paragraphs(tmp_path: Path) -> None:
    founders = {
        "proprietary": True,
        "private": True,
        "kind": "founders_note",
        "report_date": "2026-07-09",
        "founders_note_summary": (
            "A" * 400 + " proprietary paragraph that must not appear verbatim in brief output."
        ),
        "call_wall": 6300.0,
        "put_wall": 6150.0,
    }
    flow = {
        "proprietary": True,
        "private": True,
        "kind": "flowpatrol",
        "report_date": "2026-07-09",
        "executive_summary_bullets": ["Index positioning skewed bullish on delta"],
        "top_symbols": ["AAPL", "NVDA"],
    }
    sanitized = build_sanitized_advisory_context(
        founders_note=founders,
        flowpatrol=flow,
    )
    summary = sanitized["operator_safe_summary"]
    assert founders["founders_note_summary"] not in summary
    assert len(summary) < 500
    assert "investment advice" not in summary.lower()


def test_parser_output_path_must_be_private_parsed(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        assert_private_output_path(tmp_path / "data" / "founders_note.json", base_dir=tmp_path)
    ok = tmp_path / "private" / "parsed" / "spotgamma" / "founders_note_2026_07_09.json"
    assert_private_output_path(ok, base_dir=tmp_path)


def test_raw_pdf_path_must_be_private_raw(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        assert_private_raw_pdf_path(tmp_path / "founders_note.pdf", base_dir=tmp_path)
    ok = tmp_path / "private" / "raw" / "spotgamma" / "founders_note_2026_07_09.pdf"
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
        "kind": "flowpatrol",
        "report_date": "2026-07-09",
        "directional_positioning_table": [{"symbol": "SPY", "delta_mm": 1200, "percentile": 88}],
        "top_symbols": ["SPY"],
    }
    sanitized = build_sanitized_advisory_context(flowpatrol=flow)
    dumped = str(sanitized)
    assert "directional_positioning_table" not in dumped
    assert "private/raw" not in dumped
