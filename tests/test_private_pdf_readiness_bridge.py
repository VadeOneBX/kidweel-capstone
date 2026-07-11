"""PRIVATE-PDF-READINESS-BRIDGE-AUDIT-C1: private parsed JSON → morning_regime_status lanes."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from qops.advisory.private_context_builder import (
    build_sanitized_advisory_context,
    discover_private_parsed_paths,
    load_sanitized_private_context,
)
from qops.advisory.run_advisory import _build_morning_regime_status, _morning_macro_context
from qops.advisory.am_note_gate import MacroContextAudit, MacroPaperGate
from qops.runtime.orb_manifest import OrbRunManifest
from qops.schemas.candidate_loop import CandidateLoopStatus


def _gate_missing() -> MacroPaperGate:
    return MacroPaperGate(
        am_note_status="NOT_AVAILABLE",
        macro_context_state="PRE_AM_NOTE_CONTEXT_INCOMPLETE",
        paper_gate_macro_status="am_note_missing",
        macro_context_summary="missing",
        dealer_positioning_summary="",
        macro_catalyst_summary="",
        spread_posture="",
        am_note_required_before_paper=False,
        paper_approval_allowed=True,
        macro_context=MacroContextAudit(
            status="MACRO_CONTEXT_MISSING_NON_BLOCKING",
            source_type="missing",
            parse_status="MISSING_OPTIONAL_CONTEXT",
            confidence="LOW",
        ),
    )


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_a_macro_parsed_json_discovered_by_run_date(tmp_path: Path) -> None:
    parsed = tmp_path / "private" / "parsed"
    macro_path = parsed / "macro_note_2026_07_10.json"
    _write_json(
        macro_path,
        {
            "kind": "macro_note",
            "report_date": "2026-07-10",
            "parse_confidence": "HIGH",
            "macro_theme": "Risk-off tone",
            "macro_note_summary": "Summary body for bridge test.",
            "call_wall": 7600.0,
            "put_wall": 7300.0,
            "volatility_trigger": 7495.0,
            "proprietary": True,
            "private": True,
        },
    )
    found_macro, _ = discover_private_parsed_paths(tmp_path, run_date="2026-07-10")
    assert found_macro == macro_path
    ctx = load_sanitized_private_context(tmp_path, run_date="2026-07-10")
    assert ctx["lanes"]["macro_context"] != "MISSING_NON_BLOCKING"
    assert ctx["lanes"]["macro_context"] in {"READY", "READY_LOW_CONFIDENCE", "PARTIAL"}
    assert "macro_note_2026_07_10.json" in str(ctx["sources"]["macro_note"])


def test_b_flow_parsed_json_ready_with_bullets_even_if_report_date_blank(tmp_path: Path) -> None:
    """Live 2026_07_10 flow had bullets/symbols but empty report_date — must not PARSE_FAILED."""
    _write_json(
        tmp_path / "private" / "parsed" / "flow_report_2026_07_10.json",
        {
            "kind": "flow_report",
            "report_date": "",
            "parse_confidence": "MEDIUM",
            "overview_bullets": ["Bullet one", "Bullet two"],
            "top_symbols": ["AAPL", "NVDA"],
            "proprietary": True,
            "private": True,
        },
    )
    ctx = load_sanitized_private_context(tmp_path, run_date="2026-07-10")
    assert ctx["lanes"]["flow_context"] in {"READY", "READY_LOW_CONFIDENCE", "PARTIAL"}
    assert ctx["lanes"]["flow_context"] != "PARSE_FAILED_NON_BLOCKING"
    assert ctx["lanes"]["flow_context"] != "MISSING_NON_BLOCKING"


def test_c_needs_review_is_not_missing() -> None:
    lanes = build_sanitized_advisory_context(
        macro_note={
            "parse_status": "NEEDS_REVIEW",
            "parse_confidence": "LOW",
            "report_date": "",
            "proprietary": True,
            "private": True,
        },
        flow_report=None,
    )["lanes"]
    assert lanes["macro_context"] == "PARSE_FAILED_NON_BLOCKING"
    assert lanes["macro_context"] != "MISSING_NON_BLOCKING"
    # morning status must surface private PARSE_FAILED, not fall through to MISSING
    status = _morning_macro_context(_gate_missing(), lanes)
    assert status == "PARSE_FAILED_NON_BLOCKING"


def test_d_missing_artifact_remains_non_blocking(tmp_path: Path) -> None:
    ctx = load_sanitized_private_context(tmp_path, run_date="2026-07-10")
    assert ctx["lanes"]["macro_context"] == "MISSING_NON_BLOCKING"
    assert ctx["lanes"]["flow_context"] == "MISSING_NON_BLOCKING"


def test_e_hydration_remains_separate_from_private_lanes(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "private" / "parsed" / "macro_note_2026_07_10.json",
        {
            "kind": "macro_note",
            "report_date": "2026-07-10",
            "parse_confidence": "HIGH",
            "macro_theme": "Theme",
            "macro_note_summary": "Summary",
            "call_wall": 1.0,
            "put_wall": 2.0,
            "volatility_trigger": 3.0,
            "proprietary": True,
            "private": True,
        },
    )
    _write_json(
        tmp_path / "private" / "parsed" / "flow_report_2026_07_10.json",
        {
            "kind": "flow_report",
            "report_date": "2026-07-10",
            "parse_confidence": "HIGH",
            "overview_bullets": ["ok"],
            "top_symbols": ["SPY"],
            "proprietary": True,
            "private": True,
        },
    )
    private = load_sanitized_private_context(tmp_path, run_date="2026-07-10")
    risk = tmp_path / "risk.csv"
    pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "classification": CandidateLoopStatus.PARKED_DATA_GAP.value,
                "reject_reason": "alpaca_quote_hydration_incomplete",
                "candidate_loop_status": CandidateLoopStatus.PARKED_DATA_GAP.value,
                "hydration_status": "NO_CHAIN_AVAILABLE",
            }
        ]
    ).to_csv(risk, index=False)
    manifest = OrbRunManifest(
        run_id="2026-07-10-manual-150805",
        run_date="2026-07-10",
        run_ts=datetime(2026, 7, 10, 15, 8, 5, tzinfo=ZoneInfo("America/New_York")),
        mode="manual",
        status="ADVISORY_COMPLETE",
        risk_audit_artifact=str(risk),
    )
    status = _build_morning_regime_status(
        manifest,
        _gate_missing(),
        pd.read_csv(risk),
        pd.DataFrame(),
        private,
    )
    assert status["macro_context"] in {"READY", "READY_LOW_CONFIDENCE", "PARTIAL"}
    assert status["flow_context"] in {"READY", "READY_LOW_CONFIDENCE", "PARTIAL"}
    assert status["hydration"] == "PARKED_DATA_GAP"
    assert status["paper_action"] == "WITHHELD_DATA_GAP"
    assert "alpaca_quote_hydration_incomplete" in status["top_reasons"]


def test_macro_partial_when_theme_empty_but_levels_present() -> None:
    """Successful extract with empty theme/summary but usable levels is PARTIAL, not missing."""
    lanes = build_sanitized_advisory_context(
        macro_note={
            "kind": "macro_note",
            "report_date": "2026-07-10",
            "parse_confidence": "HIGH",
            "macro_theme": "",
            "macro_note_summary": "",
            "call_wall": 7600.0,
            "put_wall": 7300.0,
            "volatility_trigger": 7495.0,
            "proprietary": True,
            "private": True,
        }
    )["lanes"]
    assert lanes["macro_context"] == "PARTIAL"
    assert lanes["macro_context"] != "MISSING_NON_BLOCKING"
    assert lanes["vol_context"] in {"READY", "READY_LOW_CONFIDENCE", "PARTIAL"}
