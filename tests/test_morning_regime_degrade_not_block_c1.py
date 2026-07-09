"""MORNING-REGIME-DEGRADE-NOT-BLOCK-C1 — macro degrade-not-block + hydration-only credential park."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from qops.advisory.am_note_gate import build_macro_paper_gate, resolve_macro_context_priority
from qops.advisory.run_advisory import build_run_advisory
from qops.advisory.run_readiness import build_run_readiness
from qops.runtime.orb_manifest import OrbRunManifest
from qops.schemas.candidate_loop import CandidateLoopStatus


def _write_xlsx_founders_note(path: Path, prose: str) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame({0: prose.splitlines()}).to_excel(
            writer,
            sheet_name="morning_regime",
            index=False,
            header=False,
        )
        for sheet in ("unusual_options_positions", "stat_sig_positions", "flow_candidates"):
            pd.DataFrame({"symbol": ["AAPL"]}).to_excel(writer, sheet_name=sheet, index=False)


def _structured_note() -> dict[str, object]:
    return {
        "trade_date": "2026-07-08",
        "market_direction_summary": "Markets are constructive after overnight stability.",
        "overnight_risk_summary": "Overnight risk contained.",
        "dealer_support_summary": "Dealer long gamma may slow moves near support.",
        "dealer_risk_summary": "Downside may accelerate if support fails.",
        "advisory_bias": "constructive",
        "spread_posture": "retain candidates; review spreads",
        "macro_catalysts": ["CPI"],
        "call_positioning_risk": "Short-dated call positioning remains elevated.",
    }


def test_a_structured_sidecar_is_high_confidence_ready(tmp_path: Path) -> None:
    staging = tmp_path / "data/spotgamma/staging"
    staging.mkdir(parents=True)
    (staging / "2026-07-08_morning_regime.json").write_text(
        json.dumps(_structured_note()),
        encoding="utf-8",
    )
    gate = build_macro_paper_gate(tmp_path, run_id="2026-07-08-manual-093942")
    assert gate.am_note_status == "PARSED"
    assert gate.macro_readiness_status == "MACRO_CONTEXT_READY"
    assert gate.macro_context_source == "structured_sidecar"
    assert gate.paper_approval_allowed is True
    assert gate.am_note_required_before_paper is False
    assert gate.macro_blocks_run is False


def test_b_xlsx_founders_note_is_low_confidence_parsed(tmp_path: Path) -> None:
    staging = tmp_path / "data/spotgamma/staging"
    staging.mkdir(parents=True)
    workbook = staging / "2026-07-08_morning_regime.xlsx"
    prose = (
        "Founder note: markets are defensive after overnight sell-off.\n"
        "Dealers may slow downside near support but risk remains elevated.\n"
        "Retain candidates and challenge aggressive long-delta spreads."
    )
    _write_xlsx_founders_note(workbook, prose)

    gate = build_macro_paper_gate(tmp_path, run_id="2026-07-08-manual-093942")
    assert gate.am_note_status == "PARSED"
    assert gate.macro_readiness_status == "MACRO_CONTEXT_READY_LOW_CONFIDENCE"
    assert gate.macro_context_source == "xlsx_founders_note"
    assert gate.paper_approval_allowed is True
    assert gate.am_note_required_before_paper is False


def test_c_missing_am_note_is_non_blocking(tmp_path: Path) -> None:
    gate = build_macro_paper_gate(tmp_path, run_id="2026-07-08-manual-093942")
    assert gate.am_note_status == "NOT_AVAILABLE"
    assert gate.macro_readiness_status == "MACRO_CONTEXT_MISSING_NON_BLOCKING"
    assert gate.macro_context_source == "missing"
    assert gate.paper_approval_allowed is True
    assert gate.am_note_required_before_paper is False
    assert gate.macro_blocks_run is False


def test_d_unparsed_present_is_non_blocking(tmp_path: Path) -> None:
    staging = tmp_path / "data/spotgamma/staging"
    staging.mkdir(parents=True)
    (staging / "2026-07-08_morning_regime.json").write_text('{"trade_date":"2026-07-08"}', encoding="utf-8")

    gate = build_macro_paper_gate(tmp_path, run_id="2026-07-08-manual-093942")
    assert gate.am_note_status == "AVAILABLE_NOT_PARSED"
    assert gate.macro_readiness_status == "MACRO_CONTEXT_UNPARSED_NON_BLOCKING"
    assert gate.paper_approval_allowed is True


def test_e_credential_gap_parks_hydration_not_macro(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    monkeypatch.delenv("APCA_API_KEY_ID", raising=False)
    monkeypatch.delenv("APCA_API_SECRET_KEY", raising=False)

    staging = tmp_path / "data/spotgamma/staging"
    staging.mkdir(parents=True)
    (staging / "2026-07-08_morning_regime.json").write_text(
        json.dumps(_structured_note()),
        encoding="utf-8",
    )

    gate = build_macro_paper_gate(tmp_path, run_id="2026-07-08-manual-093942")
    assert gate.macro_readiness_status == "MACRO_CONTEXT_READY"
    assert gate.macro_blocks_run is False

    rows = [
        {
            "symbol": f"SYM{i}",
            "classification": CandidateLoopStatus.PARKED_DATA_GAP.value,
            "reject_reason": "credential_error:no_credential_pair",
            "data_gap_reason": "credential_error:no_credential_pair",
        }
        for i in range(49)
    ]
    risk_df = pd.DataFrame(rows)
    readiness = build_run_readiness(gate, risk_df)
    assert readiness.hydration.status == "PARKED_CREDENTIAL_ERROR"
    assert readiness.hydration.reason == "credential_error:no_credential_pair"
    assert readiness.hydration.parked_count == 49
    assert readiness.selection.status == "PARKED"
    assert readiness.selection.parked_count == 49
    assert readiness.macro.blocks_run is False


def test_f_manual_override_wins_over_workbook(tmp_path: Path) -> None:
    staging = tmp_path / "data/spotgamma/staging"
    staging.mkdir(parents=True)
    (staging / "2026-07-08_morning_regime.json").write_text(
        json.dumps(_structured_note()),
        encoding="utf-8",
    )
    override_dir = tmp_path / "data/advisory"
    override_dir.mkdir(parents=True)
    (override_dir / "2026-07-08-manual-093942_macro_context_override.json").write_text(
        json.dumps({"manual_override": True, "macro_context_state": "MANUAL_CONTEXT_OVERRIDE"}),
        encoding="utf-8",
    )

    resolution = resolve_macro_context_priority(tmp_path, run_id="2026-07-08-manual-093942")
    assert resolution.macro_context_source == "manual_override"
    assert resolution.macro_readiness_status == "MANUAL_CONTEXT_OVERRIDE"


def test_run_advisory_includes_readiness_lanes(tmp_path: Path) -> None:
    run_id = "2026-07-08-manual-093942"
    staging = tmp_path / "data/spotgamma/staging"
    staging.mkdir(parents=True)
    (staging / "2026-07-08_morning_regime.json").write_text(
        json.dumps(_structured_note()),
        encoding="utf-8",
    )

    context_path = tmp_path / "data/processed/context" / f"{run_id}_context.csv"
    context_path.parent.mkdir(parents=True)
    pd.DataFrame([{"symbol": "SPY", "trade_date": "2026-07-08"}]).to_csv(context_path, index=False)

    candidates_path = tmp_path / "data/processed/candidates" / f"{run_id}_candidates.csv"
    candidates_path.parent.mkdir(parents=True)
    pd.DataFrame([{"symbol": "AAPL"}]).to_csv(candidates_path, index=False)

    risk_path = tmp_path / "data/processed/risk" / f"{run_id}_risk_audit.csv"
    risk_path.parent.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "classification": "REJECTED_RR",
                "reject_reason": "spread_economics:insufficient_reward_risk",
            }
        ]
    ).to_csv(risk_path, index=False)

    expressions_path = tmp_path / "data/processed" / f"{run_id}_alpaca_hydration_expressions.csv"
    pd.DataFrame(
        [{"run_id": run_id, "symbol": "", "expression_id": "", "expression_status": ""}]
    ).to_csv(expressions_path, index=False)

    manifest = OrbRunManifest(
        run_id=run_id,
        run_date="2026-07-08",
        run_ts=pd.Timestamp("2026-07-08T09:39:42"),
        mode="manual",
        status="ADVISORY_COMPLETE",
        context_artifact=str(context_path),
        candidates_artifact=str(candidates_path),
        risk_audit_artifact=str(risk_path),
        expressions_artifact=str(expressions_path),
    )

    payload = build_run_advisory(tmp_path, manifest).run_advisory
    readiness = payload["run_readiness"]
    assert isinstance(readiness, dict)
    assert readiness["macro"]["status"] == "MACRO_CONTEXT_READY"
    assert payload["morning_regime_status"]["paper_action"] == "WITHHELD_QUALITY"
