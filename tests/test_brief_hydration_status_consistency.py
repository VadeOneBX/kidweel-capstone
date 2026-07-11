"""LATEST-CLAUDE-BRIEF-HYDRATION-STATUS-REVIEW-C1: brief/readiness consistency."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from qops.advisory.am_note_gate import MacroContextAudit, MacroPaperGate
from qops.advisory.claude_brief import (
    format_macro_gate_brief_section,
    generate_claude_brief,
)
from qops.advisory.dealer_structure import assess_dealer_structure
from qops.advisory.run_advisory import _build_morning_regime_status
from qops.advisory.run_readiness import (
    CMD_DIAGNOSE_HYDRATION,
    CMD_REFRESH_ADVISORY,
    CMD_VIEW_READINESS,
    build_operator_next_actions,
    format_readiness_view,
)
from qops.runtime.orb_manifest import OrbRunManifest
from qops.schemas.candidate_loop import CandidateLoopStatus


def _gate(
    *,
    am_note_required_before_paper: bool = False,
    audit_status: str = "MACRO_CONTEXT_MISSING_NON_BLOCKING",
) -> MacroPaperGate:
    return MacroPaperGate(
        am_note_status="NOT_AVAILABLE",
        macro_context_state="PRE_AM_NOTE_CONTEXT_INCOMPLETE",
        paper_gate_macro_status="am_note_missing_non_blocking",
        macro_context_summary=(
            "Optional AM Founder's Note context missing; morning loop continues with "
            "degraded macro confidence."
        ),
        dealer_positioning_summary="",
        macro_catalyst_summary="",
        spread_posture="retain candidates; macro context degraded (Founder's Note optional)",
        am_note_required_before_paper=am_note_required_before_paper,
        paper_approval_allowed=True,
        macro_context=MacroContextAudit(
            status=audit_status,  # type: ignore[arg-type]
            source_type="missing",
            parse_status="MISSING_OPTIONAL_CONTEXT",
            confidence="LOW",
            warnings=["Optional AM Founder's Note context missing; non-blocking degradation."],
        ),
    )


def _parked_morning(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "macro_context": "PARTIAL",
        "flow_context": "READY_LOW_CONFIDENCE",
        "hydration": "PARKED_DATA_GAP",
        "paper_action": "WITHHELD_DATA_GAP",
        "quality_gate": "FAIL",
        "parked_count": 43,
        "candidate_count": 43,
        "top_reasons": ["alpaca_quote_hydration_incomplete"],
        "operator_next_action": "",
        "selected_expression": None,
    }
    base.update(overrides)
    return base


def test_macro_partial_brief_does_not_claim_only_missing() -> None:
    section = format_macro_gate_brief_section(
        morning_regime_status=_parked_morning(),
        advisory_payload={
            "am_note_status": "NOT_AVAILABLE",
            "macro_context_state": "PRE_AM_NOTE_CONTEXT_INCOMPLETE",
            "paper_gate_macro_status": "am_note_missing_non_blocking",
            "am_note_required_before_paper": False,
            "macro_context_summary": (
                "Optional AM Founder's Note context missing; morning loop continues "
                "with degraded macro confidence."
            ),
            "macro_context_audit": {
                "status": "MACRO_CONTEXT_MISSING_NON_BLOCKING",
                "parse_status": "MISSING_OPTIONAL_CONTEXT",
                "source_type": "missing",
            },
            "private_vendor_context": {
                "lanes": {"macro_context": "PARTIAL", "flow_context": "READY_LOW_CONFIDENCE"},
                "parse_confidence": {"macro_note": "HIGH", "flow_report": "MEDIUM"},
                "sources": {"source_date": "2026_07_10"},
            },
        },
    )
    assert "Private macro context is PARTIAL" in section
    assert "Founder's Note prose remains missing or incomplete" in section
    assert "Morning loop continues with degraded macro confidence" in section
    assert "Canonical lane (`morning_regime_status.macro_context`): `PARTIAL`" in section
    assert "MACRO_CONTEXT_MISSING_NON_BLOCKING" in section  # audit field still shown
    assert "macro context is missing" not in section.lower()


def test_am_note_not_required_brief_avoids_required_before_paper_wording() -> None:
    section = format_macro_gate_brief_section(
        morning_regime_status=_parked_morning(),
        advisory_payload={
            "am_note_status": "NOT_AVAILABLE",
            "macro_context_state": "PRE_AM_NOTE_CONTEXT_INCOMPLETE",
            "paper_gate_macro_status": "am_note_missing_non_blocking",
            "am_note_required_before_paper": False,
            "macro_context_summary": "Optional AM Founder's Note context missing.",
            "dealer_positioning_summary": (
                "Pre-AM note structure recorded from SpotGamma; Founder's Note prose "
                "remains optional low-confidence enrichment."
            ),
            "macro_context_audit": {
                "status": "MACRO_CONTEXT_MISSING_NON_BLOCKING",
                "parse_status": "MISSING_OPTIONAL_CONTEXT",
                "source_type": "missing",
            },
            "dealer_structure": {
                "structure_summary": (
                    "Pre-AM note structure recorded from SpotGamma; Founder's Note prose "
                    "remains optional low-confidence enrichment."
                ),
                "advisory_bias": "SELECTIVE_LONG_DELTA",
                "gamma_regime": "POSITIVE_GAMMA_STABLE",
            },
        },
    )
    assert "required before paper approval" not in section.lower()
    assert "am_note_required_before_paper` | `False`" in section or (
        "`am_note_required_before_paper` | `False`" in section
    )


def test_hydration_parked_actions_include_exact_commands() -> None:
    morning = _parked_morning()
    actions = build_operator_next_actions(
        morning=morning,
        private_vendor_context={
            "source_presence": {"macro_note": True, "flow_report": True},
            "lanes": {"macro_context": "PARTIAL", "flow_context": "READY_LOW_CONFIDENCE"},
        },
        stored_morning=morning,
    )
    by_id = {a["id"]: a for a in actions}
    assert by_id["diagnose_quote_hydration"]["command"] == CMD_DIAGNOSE_HYDRATION
    assert by_id["retry_hydration_via_morning_loop"]["command"] == CMD_REFRESH_ADVISORY
    assert by_id["view_readiness"]["command"] == CMD_VIEW_READINESS
    assert CMD_DIAGNOSE_HYDRATION == (
        "uv run python scripts/alpaca_fetch.py --env-check"
    )


def test_no_empty_operator_next_action_when_hydration_parked(tmp_path: Path) -> None:
    risk_path = tmp_path / "risk.csv"
    risk = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "classification": CandidateLoopStatus.PARKED_DATA_GAP.value,
                "reject_reason": "alpaca_quote_hydration_incomplete",
                "candidate_loop_status": CandidateLoopStatus.PARKED_DATA_GAP.value,
            }
        ]
        * 3
    )
    risk.to_csv(risk_path, index=False)
    manifest = OrbRunManifest(
        run_id="2026-07-10-manual-202905",
        run_date="2026-07-10",
        run_ts=datetime(2026, 7, 10, 20, 29, 5, tzinfo=ZoneInfo("America/New_York")),
        mode="manual",
        status="ADVISORY_COMPLETE",
        risk_audit_artifact=str(risk_path),
    )
    private = {
        "lanes": {
            "macro_context": "PARTIAL",
            "flow_context": "READY_LOW_CONFIDENCE",
            "skew_context": "PARTIAL",
            "vol_context": "READY",
            "index_levels_context": "PARTIAL",
        },
        "source_presence": {"macro_note": True, "flow_report": True},
    }
    status = _build_morning_regime_status(
        manifest,
        _gate(),
        risk,
        pd.DataFrame(),
        private,
    )
    assert status["hydration"] == "PARKED_DATA_GAP"
    assert status["parked_count"] > 0
    assert status["operator_next_action"], (
        "operator_next_action must not be empty when hydration is parked"
    )
    action_blob = str(status["operator_next_action"]).lower()
    assert "uv run" in action_blob
    for vague in (
        "re-run morning advisory",
        "resolve hydration",
        "try again",
        "check the data",
        "fix hydration",
    ):
        assert vague not in action_blob
    actions = status.get("operator_next_actions")
    assert isinstance(actions, list) and actions
    assert all(str(a.get("command", "")).startswith("uv run") for a in actions)


def test_dealer_structure_does_not_require_founder_note_for_paper() -> None:
    context = pd.DataFrame(
        [
            {
                "symbol": "SPY",
                "trade_date": "2026-07-09",
                "gamma_ratio": 1.2,
                "iv_rank": 40.0,
                "notes": (
                    "current_price=600|call_wall=610|put_wall=590|hedge_wall=595|"
                    "one_month_iv=0.18|one_month_rv=0.15"
                ),
                "source_profile": "spy_excel",
            },
            {
                "symbol": "SPY",
                "trade_date": "2026-07-10",
                "gamma_ratio": 1.25,
                "iv_rank": 41.0,
                "notes": (
                    "current_price=601|call_wall=610|put_wall=590|hedge_wall=595|"
                    "one_month_iv=0.18|one_month_rv=0.15"
                ),
                "source_profile": "spy_excel",
            },
        ]
    )
    assessment = assess_dealer_structure(context)
    assert "required before paper approval" not in assessment.structure_summary.lower()
    assert "still required" not in assessment.structure_summary.lower()


def test_claude_brief_hydration_and_macro_consistency(tmp_path: Path) -> None:
    processed = tmp_path / "data" / "processed"
    processed.mkdir(parents=True)
    context = processed / "context.csv"
    candidates = processed / "candidates.csv"
    risk = processed / "risk.csv"
    pd.DataFrame(
        [
            {
                "symbol": "SPY",
                "trade_date": "2026-07-10",
                "regime_label": "BALANCED",
                "structure_bias": "SKIP",
                "gamma_ratio": 1.1,
                "notes": "current_price=600|call_wall=610|put_wall=590|hedge_wall=595",
            }
        ]
    ).to_csv(context, index=False)
    pd.DataFrame([{"symbol": "AAPL"}]).to_csv(candidates, index=False)
    pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "classification": CandidateLoopStatus.PARKED_DATA_GAP.value,
                "paper_approval_status": "PENDING",
                "candidate_loop_status": CandidateLoopStatus.PARKED_DATA_GAP.value,
                "reject_reason": "alpaca_quote_hydration_incomplete",
                "data_gap_reason": "alpaca_quote_hydration_incomplete",
                "hydration_status": "NO_CHAIN_AVAILABLE",
            }
        ]
        * 3
    ).to_csv(risk, index=False)

    parsed = tmp_path / "private" / "parsed"
    parsed.mkdir(parents=True)
    (parsed / "macro_note_2026_07_10.json").write_text(
        json.dumps(
            {
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
        ),
        encoding="utf-8",
    )
    (parsed / "flow_report_2026_07_10.json").write_text(
        json.dumps(
            {
                "kind": "flow_report",
                "report_date": "2026-07-10",
                "parse_confidence": "MEDIUM",
                "overview_bullets": ["Flow bullet"],
                "top_symbols": ["AAPL", "NVDA"],
                "proprietary": True,
                "private": True,
            }
        ),
        encoding="utf-8",
    )

    manifest = OrbRunManifest(
        run_id="2026-07-10-manual-202905",
        run_date="2026-07-10",
        run_ts=datetime(2026, 7, 10, 20, 29, 5, tzinfo=ZoneInfo("America/New_York")),
        mode="manual",
        status="ADVISORY_COMPLETE",
        context_artifact=str(context),
        candidates_artifact=str(candidates),
        risk_audit_artifact=str(risk),
        live_mode_enabled=False,
        broker_mutation_occurred=False,
    )
    result = generate_claude_brief(tmp_path, manifest)
    body = Path(result.advisory_artifact).read_text(encoding="utf-8")
    assert "Private macro context is PARTIAL" in body
    assert "required before paper approval" not in body.lower()
    assert "Selected is still reviewed" in body
    assert "Selected is not optimal" not in body
    assert "Attractive is not approved" in body
    assert "uv run python scripts/alpaca_fetch.py --env-check" in body
    assert "uv run python scripts/orb_morning_loop.py --mode manual --base-dir ." in body
    assert "uv run python scripts/operator_status.py --base-dir . --readiness" in body
    assert "flow_context: `READY_LOW_CONFIDENCE`" in body
    assert "source_date" in body.lower() or "2026_07_10" in body or "2026-07-10" in body
    # morning_regime remains canonical lane
    assert "macro_context: `PARTIAL`" in body
    assert "paper_action: `WITHHELD_DATA_GAP`" in body


def test_env_check_is_symbol_free() -> None:
    import importlib.util

    path = Path(__file__).resolve().parents[1] / "scripts" / "alpaca_fetch.py"
    spec = importlib.util.spec_from_file_location("alpaca_fetch_cli", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    args = mod.parse_args(["--env-check"])
    assert args.env_check is True
    assert not getattr(args, "symbols", None)


def test_readiness_view_hydration_commands_not_empty() -> None:
    view = format_readiness_view(
        run_id="2026-07-10-manual-202905",
        morning_regime_status=_parked_morning(),
        macro_context_audit={
            "status": "MACRO_CONTEXT_MISSING_NON_BLOCKING",
            "source_type": "missing",
            "parse_status": "MISSING_OPTIONAL_CONTEXT",
        },
        private_vendor_context={
            "source_presence": {"macro_note": True, "flow_report": True},
            "lanes": {"macro_context": "PARTIAL", "flow_context": "READY_LOW_CONFIDENCE"},
            "sources": {"source_date": "2026_07_10"},
        },
    )
    assert view["morning_regime_status"]["macro_context"] == "PARTIAL"
    assert view["operator_next_action"]
    assert all(isinstance(s, str) and s.startswith(("diagnose_", "retry_", "view_")) for s in view["operator_next_action"])
    cmds = [a["command"] for a in view["operator_next_actions"]]
    assert CMD_DIAGNOSE_HYDRATION in cmds
    assert CMD_REFRESH_ADVISORY in cmds
    assert CMD_VIEW_READINESS in cmds
