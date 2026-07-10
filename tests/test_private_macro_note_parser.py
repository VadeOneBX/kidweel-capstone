"""Tests for private macro note parser."""

from __future__ import annotations

from pathlib import Path

from qops.advisory.private_macro_note_parser import parse_macro_note_text


def _fixture_text() -> str:
    return (
        Path(__file__).parent / "fixtures" / "private_vendor_samples" / "macro_note_sample_fixture.txt"
    ).read_text(encoding="utf-8")


def test_macro_note_date_parsed() -> None:
    parsed = parse_macro_note_text(_fixture_text())
    assert parsed["report_date"] == "2026-07-09"
    assert parsed["report_time"] == "8:00 AM ET"


def test_macro_note_key_dates_parsed() -> None:
    parsed = parse_macro_note_text(_fixture_text())
    key_dates = parsed["key_dates"]
    assert "2026-07-10" in key_dates
    assert "2026-07-16" in key_dates


def test_macro_note_index_levels_parsed() -> None:
    parsed = parse_macro_note_text(_fixture_text())
    levels = parsed["index_levels"]
    assert levels["resistance"] == 6280.0
    assert levels["pivot"] == 6220.0
    assert levels["support"] == 6180.0


def test_macro_note_dealer_levels_parsed() -> None:
    parsed = parse_macro_note_text(_fixture_text())
    assert parsed["call_wall"] == 6300.0
    assert parsed["put_wall"] == 6150.0
    assert parsed["zero_gamma_level"] == 6225.0
    assert parsed["volatility_trigger"] == 6180.0
    assert parsed["absolute_gamma_strike"] == 6225.0


def test_macro_note_risk_reversal_parsed() -> None:
    parsed = parse_macro_note_text(_fixture_text())
    assert parsed["risk_reversal_25d"] == -2.5


def test_macro_note_output_marked_proprietary() -> None:
    parsed = parse_macro_note_text(_fixture_text())
    assert parsed["proprietary"] is True
    assert parsed["private"] is True
    assert parsed["kind"] == "macro_note"


def test_macro_note_macro_and_skew_fields() -> None:
    parsed = parse_macro_note_text(_fixture_text())
    assert "Range-bound" in parsed["macro_theme"]
    assert "Put skew" in parsed["skew_commentary"]
    assert parsed["implied_1d_move_pct"] == 0.85
    assert parsed["implied_5d_move_pct"] == 2.10


def test_macro_note_weekday_header_date_parsed() -> None:
    alt = (
        Path(__file__).parent / "fixtures" / "private_vendor_samples" / "macro_note_alt_date_fixture.txt"
    ).read_text(encoding="utf-8")
    parsed = parse_macro_note_text(alt)
    assert parsed["report_date"] == "2026-07-09"
    assert parsed["report_time"] == "8:00 AM ET"
    assert "Range-bound" in parsed["macro_theme"]
    assert "Key dates ahead" not in parsed["macro_theme"]
    assert parsed["macro_note_summary"]
    assert parsed["call_wall"] == 7600.0
    assert parsed["put_wall"] == 7300.0
    assert parsed["parse_confidence"] in {"HIGH", "MEDIUM"}


def test_sanitized_lanes_ready_with_alt_date_fixture() -> None:
    from qops.advisory.private_context_builder import build_sanitized_advisory_context

    alt = (
        Path(__file__).parent / "fixtures" / "private_vendor_samples" / "macro_note_alt_date_fixture.txt"
    ).read_text(encoding="utf-8")
    parsed = parse_macro_note_text(alt)
    sanitized = build_sanitized_advisory_context(macro_note=parsed)
    lanes = sanitized["lanes"]
    assert lanes["macro_context"] in {"READY", "READY_LOW_CONFIDENCE", "PARTIAL"}
    assert lanes["index_levels_context"] in {"READY", "READY_LOW_CONFIDENCE"}
    assert sanitized["gate_levels"]["call_wall"] == 7600.0
