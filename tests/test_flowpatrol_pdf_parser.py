"""Tests for FlowPatrol PDF/text parser."""

from __future__ import annotations

from pathlib import Path

from qops.advisory.flowpatrol_parser import parse_flowpatrol_text


def _fixture_text() -> str:
    return (Path(__file__).parent / "fixtures" / "sg_pdf_samples" / "fp_sample_fixture.txt").read_text(
        encoding="utf-8"
    )


def test_flowpatrol_report_date_parsed() -> None:
    parsed = parse_flowpatrol_text(_fixture_text())
    assert parsed["report_date"] == "2026-07-09"


def test_flowpatrol_executive_summary_parsed() -> None:
    parsed = parse_flowpatrol_text(_fixture_text())
    bullets = parsed["executive_summary_bullets"]
    assert len(bullets) >= 2
    assert any("bullish" in b.lower() for b in bullets)


def test_flowpatrol_stat_sig_positions_parsed() -> None:
    parsed = parse_flowpatrol_text(_fixture_text())
    rows = parsed["statistically_significant_positions"]
    symbols = {row["symbol"] for row in rows}
    assert "AAPL" in symbols
    assert "NVDA" in symbols
    aapl = next(r for r in rows if r["symbol"] == "AAPL")
    assert aapl["delta_mm"] == 12.5
    assert aapl["delta_percentile"] == 95


def test_flowpatrol_sector_stats_parsed() -> None:
    parsed = parse_flowpatrol_text(_fixture_text())
    stats = parsed["sector_statistical_analysis"]
    assert any(s["sector"] == "Technology" for s in stats)


def test_flowpatrol_top_symbols_parsed() -> None:
    parsed = parse_flowpatrol_text(_fixture_text())
    symbols = parsed["top_symbols"]
    assert "AAPL" in symbols
    assert "NVDA" in symbols


def test_flowpatrol_output_marked_proprietary() -> None:
    parsed = parse_flowpatrol_text(_fixture_text())
    assert parsed["proprietary"] is True
    assert parsed["private"] is True
    assert parsed["kind"] == "flowpatrol"
