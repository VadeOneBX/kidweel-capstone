"""Tests for private flow report parser."""

from __future__ import annotations

from pathlib import Path

from qops.advisory.private_flow_report_parser import parse_flow_report_text


def _fixture_text() -> str:
    return (
        Path(__file__).parent / "fixtures" / "private_vendor_samples" / "flow_report_sample_fixture.txt"
    ).read_text(encoding="utf-8")


def test_flow_report_date_parsed() -> None:
    parsed = parse_flow_report_text(_fixture_text())
    assert parsed["report_date"] == "2026-07-09"


def test_flow_report_overview_parsed() -> None:
    parsed = parse_flow_report_text(_fixture_text())
    bullets = parsed["overview_bullets"]
    assert len(bullets) >= 2
    assert any("bullish" in b.lower() for b in bullets)


def test_flow_report_notable_positions_parsed() -> None:
    parsed = parse_flow_report_text(_fixture_text())
    rows = parsed["notable_positions"]
    symbols = {row["symbol"] for row in rows}
    assert "AAPL" in symbols
    assert "NVDA" in symbols
    aapl = next(r for r in rows if r["symbol"] == "AAPL")
    assert aapl["delta_mm"] == 12.5
    assert aapl["delta_percentile"] == 95


def test_flow_report_sector_stats_parsed() -> None:
    parsed = parse_flow_report_text(_fixture_text())
    stats = parsed["sector_stats"]
    assert any(s["sector"] == "Technology" for s in stats)


def test_flow_report_top_symbols_parsed() -> None:
    parsed = parse_flow_report_text(_fixture_text())
    symbols = parsed["top_symbols"]
    assert "AAPL" in symbols
    assert "NVDA" in symbols


def test_flow_report_output_marked_proprietary() -> None:
    parsed = parse_flow_report_text(_fixture_text())
    assert parsed["proprietary"] is True
    assert parsed["private"] is True
    assert parsed["kind"] == "flow_report"


def test_flow_report_legacy_section_headers_parsed() -> None:
    legacy = (
        Path(__file__).parent
        / "fixtures"
        / "private_vendor_samples"
        / "flow_report_legacy_sections_fixture.txt"
    ).read_text(encoding="utf-8")
    parsed = parse_flow_report_text(legacy)
    assert parsed["report_date"] == "2026-07-09"
    assert len(parsed["overview_bullets"]) >= 2
    assert parsed["top_symbols"]
    assert "AAPL" in parsed["top_symbols"]
    assert parsed["notable_positions"]
    assert parsed["parse_confidence"] in {"HIGH", "MEDIUM"}
    assert "https://" not in str(parsed["algo_flow"])


def test_sanitized_flow_lanes_with_legacy_fixture() -> None:
    from qops.advisory.private_context_builder import build_sanitized_advisory_context

    legacy = (
        Path(__file__).parent
        / "fixtures"
        / "private_vendor_samples"
        / "flow_report_legacy_sections_fixture.txt"
    ).read_text(encoding="utf-8")
    parsed = parse_flow_report_text(legacy)
    sanitized = build_sanitized_advisory_context(flow_report=parsed)
    assert sanitized["lanes"]["flow_context"] in {"READY", "READY_LOW_CONFIDENCE", "PARTIAL"}
    assert sanitized["top_symbols"]
