"""Tests for Founder Note PDF/text parser."""

from __future__ import annotations

from pathlib import Path

from qops.advisory.founders_note_parser import parse_founders_note_text


def _fixture_text() -> str:
    return (Path(__file__).parent / "fixtures" / "sg_pdf_samples" / "fn_sample_fixture.txt").read_text(
        encoding="utf-8"
    )


def test_founders_note_date_parsed() -> None:
    parsed = parse_founders_note_text(_fixture_text())
    assert parsed["report_date"] == "2026-07-09"
    assert parsed["report_time"] == "8:00 AM ET"


def test_founders_note_key_dates_parsed() -> None:
    parsed = parse_founders_note_text(_fixture_text())
    key_dates = parsed["key_dates"]
    assert "2026-07-10" in key_dates
    assert "2026-07-16" in key_dates


def test_founders_note_spx_levels_parsed() -> None:
    parsed = parse_founders_note_text(_fixture_text())
    levels = parsed["key_spx_levels"]
    assert levels["resistance"] == 6280.0
    assert levels["pivot"] == 6220.0
    assert levels["support"] == 6180.0


def test_founders_note_dealer_levels_parsed() -> None:
    parsed = parse_founders_note_text(_fixture_text())
    assert parsed["call_wall"] == 6300.0
    assert parsed["put_wall"] == 6150.0
    assert parsed["zero_gamma_level"] == 6225.0
    assert parsed["volatility_trigger"] == 6180.0
    assert parsed["absolute_gamma_strike"] == 6225.0


def test_founders_note_risk_reversal_parsed() -> None:
    parsed = parse_founders_note_text(_fixture_text())
    assert parsed["risk_reversal_25d"] == -2.5


def test_founders_note_output_marked_proprietary() -> None:
    parsed = parse_founders_note_text(_fixture_text())
    assert parsed["proprietary"] is True
    assert parsed["private"] is True
    assert parsed["kind"] == "founders_note"


def test_founders_note_macro_and_skew_fields() -> None:
    parsed = parse_founders_note_text(_fixture_text())
    assert "Range-bound" in parsed["macro_theme"]
    assert "Put skew" in parsed["skew_commentary"]
    assert parsed["sg_implied_1d_move_pct"] == 0.85
    assert parsed["sg_implied_5d_move_pct"] == 2.10
