"""MORNING-REGIME-DEGRADE-NOT-BLOCK-C1: macro context degrades; does not hard-block."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from qops.advisory.am_note_gate import (
    build_macro_paper_gate,
    parse_xlsx_founders_note,
)
from qops.advisory.run_advisory import build_run_advisory
from qops.advisory.run_readiness import format_readiness_view
from qops.risk.guard_runner import run_risk_guard
from qops.risk.paper_approval import SpreadCandidateInputRow
from qops.runtime.orb_manifest import OrbRunManifest


def _write_founders_xlsx(path: Path, *, include_label: bool = True, prose: str = "") -> Path:
    note = prose or (
        "Futures are off 50bps as the Iran war re-flames. WTI is +2.5% to 74.5. "
        "Positive gamma still dominates in the SPX."
    )
    rows: list[list[object]] = [
        ["Macro Theme:"],
        ["Key dates ahead:"],
        ["7/8: FOMC Mins"],
    ]
    if include_label:
        rows.extend([["Founder's Note:"], [note], ["What Traders Should Know Today"]])
    else:
        rows.append(["SG Summary:"])
        rows.append(["No founder section in this workbook."])
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_excel(path, index=False, header=False, sheet_name="morning_regime")
    return path


def _structured_note(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "trade_date": "2026-07-08",
        "market_direction_summary": "Markets are soft after overnight weakness.",
        "overnight_risk_summary": "Geopolitical risk overnight.",
        "dealer_support_summary": "Positive gamma may slow dips.",
        "dealer_risk_summary": "Negative gamma opens below key support.",
        "advisory_bias": "defensive",
        "spread_posture": "retain candidates, challenge long-delta spreads",
        "macro_catalysts": ["FOMC minutes"],
        "call_positioning_risk": "Elevated short-dated call risk.",
    }
    base.update(overrides)
    return base


def _passing_spread_row(**overrides: object) -> SpreadCandidateInputRow:
    base = dict(
        structure_type="BULL_CALL_SPREAD",
        underlying_symbol="IBIT",
        trade_date="2026-07-08",
        expiration="2026-07-11",
        long_option_symbol="IBIT260711C00036500",
        short_option_symbol="IBIT260711C00037000",
        spread_width=0.5,
        net_debit_or_credit=0.12,
        pmp_for_gate=0.35,
        pmp_source="short_leg_delta_proxy",
        pmp_confidence="LOW",
        max_profit=0.38,
        max_loss=0.12,
        reward_risk=3.16,
        break_even=36.62,
        capital_at_risk=0.12,
        passes_spread_math_gate=True,
        probability_status="PASS",
        ev_status="PASS",
        candidate_pass=True,
        failure_reasons="",
        provenance="test",
    )
    base.update(overrides)
    return SpreadCandidateInputRow(**base)  # type: ignore[arg-type]


def test_a_structured_sidecar_wins_over_xlsx_founders_note(tmp_path: Path) -> None:
    staging = tmp_path / "data/spotgamma/staging"
    staging.mkdir(parents=True)
    _write_founders_xlsx(staging / "2026-07-08_morning_regime.xlsx")
    sidecar = staging / "2026-07-08_morning_regime.json"
    sidecar.write_text(json.dumps(_structured_note()), encoding="utf-8")

    gate = build_macro_paper_gate(tmp_path, run_id="2026-07-08-manual-test")
    assert gate.macro_context.status == "MACRO_CONTEXT_READY"
    assert gate.macro_context.source_type == "structured_sidecar"
    assert gate.macro_context.parse_status == "STRUCTURED_PARSED"
    assert gate.macro_context.source_file.endswith("2026-07-08_morning_regime.json")
    assert gate.parsed_note is not None
    assert gate.parsed_note.advisory_bias == "defensive"
    assert gate.paper_approval_allowed is True


def test_b_xlsx_founders_note_fallback_low_confidence(tmp_path: Path) -> None:
    staging = tmp_path / "data/spotgamma/staging"
    staging.mkdir(parents=True)
    xlsx = _write_founders_xlsx(staging / "2026-07-08_morning_regime.xlsx")

    gate = build_macro_paper_gate(tmp_path, run_id="2026-07-08-manual-test")
    assert gate.macro_context.parse_status == "XLSX_FOUNDER_NOTE_PARSED"
    assert gate.macro_context.source_type == "xlsx_founders_note"
    assert gate.macro_context.status == "MACRO_CONTEXT_READY_LOW_CONFIDENCE"
    assert gate.macro_context.confidence == "LOW"
    assert any(
        "workbook prose fallback" in w and "structured AM-note sidecar not present" in w
        for w in gate.macro_context.warnings
    )
    assert gate.parsed_note is not None
    assert gate.parsed_note.advisory_bias in {"", "UNKNOWN"}
    assert gate.parsed_note.spread_posture in {"", "UNKNOWN"}
    assert "Futures are off" in (gate.parsed_note.market_direction_summary or "")
    assert gate.am_note_required_before_paper is False
    assert Path(gate.macro_context.source_file).resolve() == xlsx.resolve()


def test_c_xlsx_present_but_unparseable_degrades_non_blocking(tmp_path: Path) -> None:
    staging = tmp_path / "data/spotgamma/staging"
    staging.mkdir(parents=True)
    _write_founders_xlsx(staging / "2026-07-08_morning_regime.xlsx", include_label=False)

    gate = build_macro_paper_gate(tmp_path, run_id="2026-07-08-manual-test")
    assert gate.macro_context.parse_status == "AVAILABLE_NOT_PARSED"
    assert gate.macro_context.status == "MACRO_CONTEXT_UNPARSED_NON_BLOCKING"
    assert gate.am_note_required_before_paper is False
    assert gate.paper_approval_allowed is True


def test_d_missing_am_note_degrades_non_blocking(tmp_path: Path) -> None:
    gate = build_macro_paper_gate(tmp_path, run_id="2026-07-08-manual-test")
    assert gate.macro_context.status == "MACRO_CONTEXT_MISSING_NON_BLOCKING"
    assert gate.macro_context.parse_status in {"NOT_AVAILABLE", "MISSING_OPTIONAL_CONTEXT"}
    assert gate.am_note_required_before_paper is False
    assert gate.paper_approval_allowed is True


def test_e_manual_override_wins_over_sidecar_and_xlsx(tmp_path: Path) -> None:
    staging = tmp_path / "data/spotgamma/staging"
    advisory = tmp_path / "data/advisory"
    staging.mkdir(parents=True)
    advisory.mkdir(parents=True)
    _write_founders_xlsx(staging / "2026-07-08_morning_regime.xlsx")
    (staging / "2026-07-08_morning_regime.json").write_text(
        json.dumps(_structured_note()),
        encoding="utf-8",
    )
    override_path = advisory / "2026-07-08-manual-test_macro_context_override.json"
    override_path.write_text(
        json.dumps(
            {
                "manual_override": True,
                "macro_context_state": "MANUAL_CONTEXT_OVERRIDE",
                "parsed_note": {
                    "market_direction_summary": "Operator override direction.",
                    "dealer_support_summary": "Operator override support.",
                    "dealer_risk_summary": "Operator override risk.",
                    "advisory_bias": "neutral",
                    "spread_posture": "retain candidates",
                },
            }
        ),
        encoding="utf-8",
    )

    gate = build_macro_paper_gate(tmp_path, run_id="2026-07-08-manual-test")
    assert gate.macro_context.source_type == "manual_macro_context_override"
    assert gate.macro_context.parse_status == "MANUAL_OVERRIDE_PARSED"
    assert any("Manual macro context override used." in w for w in gate.macro_context.warnings)
    assert gate.macro_context.source_file.endswith("_macro_context_override.json")
    assert gate.paper_approval_allowed is True


def test_f_credential_error_isolated_from_macro_context(tmp_path: Path) -> None:
    staging = tmp_path / "data/spotgamma/staging"
    staging.mkdir(parents=True)
    _write_founders_xlsx(staging / "2026-07-08_morning_regime.xlsx")

    candidates = tmp_path / "spread_candidates.csv"
    pd.DataFrame([asdict(_passing_spread_row())]).to_csv(candidates, index=False)
    # Credential gaps may appear only on risk audit when expressions CSV is absent.
    expressions = tmp_path / "expressions_missing.csv"

    risk = run_risk_guard(
        tmp_path,
        run_id="2026-07-08-manual-test",
        candidates_artifact=str(candidates),
    )
    audit = pd.read_csv(risk.risk_audit_artifact)
    assert "PAPER_GATE_WITHHELD" not in set(audit["classification"].astype(str))
    # Force credential marker onto audit for lane isolation (matches live parked path).
    audit["data_gap_reason"] = "credential_error:no_credential_pair"
    audit["reject_reason"] = "credential_error:no_credential_pair"
    audit["candidate_loop_status"] = "PARKED_DATA_GAP"
    audit.to_csv(risk.risk_audit_artifact, index=False)

    gate = build_macro_paper_gate(tmp_path, run_id="2026-07-08-manual-test")
    assert gate.macro_context.status == "MACRO_CONTEXT_READY_LOW_CONFIDENCE"

    # Upstream spine: hydration credential park must not rewrite macro_context lane.
    assert gate.macro_context.status == "MACRO_CONTEXT_READY_LOW_CONFIDENCE"
    assert "credential" not in gate.macro_context.status.lower()

    (tmp_path / "data/processed/context").mkdir(parents=True, exist_ok=True)
    context = tmp_path / "data/processed/context/2026-07-08-manual-test_context.csv"
    pd.DataFrame([{"symbol": "SPY", "trade_date": "2026-07-08"}]).to_csv(context, index=False)
    manifest = OrbRunManifest(
        run_id="2026-07-08-manual-test",
        run_date="2026-07-08",
        run_ts=pd.Timestamp("2026-07-08T09:39:42"),
        mode="manual",
        status="ADVISORY_COMPLETE",
        context_artifact=str(context),
        candidates_artifact=str(candidates),
        risk_audit_artifact=str(risk.risk_audit_artifact),
        expressions_artifact=str(expressions),
    )
    result = build_run_advisory(tmp_path, manifest).run_advisory
    status = result["morning_regime_status"]
    assert status["macro_context"] == "READY_LOW_CONFIDENCE"
    assert status["hydration"] == "PARKED_CREDENTIAL_ERROR"
    assert status["paper_action"] == "WITHHELD_CREDENTIALS"
    view = format_readiness_view(
        run_id=manifest.run_id,
        morning_regime_status=status,
        macro_context_audit=result.get("macro_context_audit"),
    )
    assert view["macro_context"]["status"] == "READY_LOW_CONFIDENCE"
    assert view["hydration"]["status"] == "PARKED_CREDENTIAL_ERROR"


def test_parse_xlsx_founders_note_label_variants(tmp_path: Path) -> None:
    for label in ("Founder's Note:", "Founders Note:", "Founder Note:", "AM Note:", "Morning Note:"):
        path = tmp_path / f"{label.replace(' ', '_').replace(':', '')}.xlsx"
        pd.DataFrame([[label], ["Prose body for variant."]]).to_excel(
            path, index=False, header=False, sheet_name="morning_regime"
        )
        parsed = parse_xlsx_founders_note(path)
        assert parsed is not None
        assert "Prose body" in parsed.market_direction_summary


def test_run_advisory_records_macro_hydration_selection_lanes(tmp_path: Path) -> None:
    staging = tmp_path / "data/spotgamma/staging"
    staging.mkdir(parents=True)
    _write_founders_xlsx(staging / "2026-07-08_morning_regime.xlsx")
    (tmp_path / "data/processed/context").mkdir(parents=True)
    (tmp_path / "data/processed/candidates").mkdir(parents=True)
    (tmp_path / "data/processed/risk").mkdir(parents=True)
    context = tmp_path / "data/processed/context/ctx.csv"
    candidates = tmp_path / "data/processed/candidates/cands.csv"
    risk = tmp_path / "data/processed/risk/risk.csv"
    expressions = tmp_path / "data/processed/expr.csv"
    pd.DataFrame([{"symbol": "SPY", "trade_date": "2026-07-08", "gamma_ratio": 1.0}]).to_csv(
        context, index=False
    )
    pd.DataFrame([asdict(_passing_spread_row())]).to_csv(candidates, index=False)
    pd.DataFrame(
        [
            {
                "classification": "PARKED_DATA_GAP",
                "paper_approval_status": "PENDING",
                "candidate_loop_status": "PARKED_DATA_GAP",
                "reject_reason": "credential_error:no_credential_pair",
            }
        ]
    ).to_csv(risk, index=False)
    pd.DataFrame(
        [
            {
                "run_id": "2026-07-08-manual-test",
                "symbol": "IBIT",
                "expression_status": "PARKED_DATA_GAP",
                "data_gap_reason": "credential_error:no_credential_pair",
            }
        ]
    ).to_csv(expressions, index=False)

    manifest = OrbRunManifest(
        run_id="2026-07-08-manual-test",
        run_date="2026-07-08",
        run_ts=datetime(2026, 7, 8, 9, 30, tzinfo=ZoneInfo("America/New_York")),
        mode="manual",
        status="RISK_GUARD_COMPLETE",
        staged_files=[str(staging / "2026-07-08_morning_regime.xlsx")],
        context_artifact=str(context),
        candidates_artifact=str(candidates),
        expressions_artifact=str(expressions),
        risk_audit_artifact=str(risk),
    )
    result = build_run_advisory(tmp_path, manifest)
    payload = result.run_advisory
    assert "morning_regime_status" in payload
    assert payload["morning_regime_status"]["macro_context"] == "READY_LOW_CONFIDENCE"
    assert payload["macro_context_audit"]["parse_status"] == "XLSX_FOUNDER_NOTE_PARSED"
    status = payload["morning_regime_status"]
    assert status["hydration"] == "PARKED_CREDENTIAL_ERROR"
    assert status["paper_action"] == "WITHHELD_CREDENTIALS"
    view = format_readiness_view(
        run_id=manifest.run_id,
        morning_regime_status=status,
        macro_context_audit=payload.get("macro_context_audit"),
    )
    assert view["macro_context"]["parse_status"] == "XLSX_FOUNDER_NOTE_PARSED"
    assert view["hydration"]["status"] == "PARKED_CREDENTIAL_ERROR"
