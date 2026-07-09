from __future__ import annotations

from pathlib import Path

import pandas as pd

from qops.advisory.run_advisory import build_run_advisory
from qops.runtime.orb_manifest import OrbRunManifest
from qops.schemas.candidate_loop import CandidateLoopStatus, SpreadExpressionStatus


def _write_csv(path: Path, rows: list[dict[str, object]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)
    return str(path)


def _manifest_with_artifacts(
    tmp_path: Path,
    run_id: str,
    *,
    context_rows: list[dict[str, object]],
    candidate_rows: list[dict[str, object]],
    risk_rows: list[dict[str, object]],
    expression_rows: list[dict[str, object]] | None = None,
    allow_paper: bool = True,
) -> OrbRunManifest:
    context_path = _write_csv(
        tmp_path / "data/processed/context" / f"{run_id}_context.csv",
        context_rows,
    )
    candidates_path = _write_csv(
        tmp_path / "data/processed/candidates" / f"{run_id}_candidates.csv",
        candidate_rows,
    )
    risk_path = _write_csv(
        tmp_path / "data/processed/risk" / f"{run_id}_risk_audit.csv",
        risk_rows,
    )
    expr_rows = expression_rows or [
        {
            "run_id": run_id,
            "symbol": "",
            "expression_id": "",
            "expression_status": "",
        }
    ]
    expressions_path = _write_csv(
        tmp_path / "data/processed" / f"{run_id}_alpaca_hydration_expressions.csv",
        expr_rows,
    )
    if allow_paper:
        override = tmp_path / "data/advisory" / f"{run_id}_macro_context_override.json"
        override.parent.mkdir(parents=True, exist_ok=True)
        override.write_text(
            '{"manual_override": true, "macro_context_state": "MANUAL_CONTEXT_OVERRIDE"}',
            encoding="utf-8",
        )
    return OrbRunManifest(
        run_id=run_id,
        run_date=run_id.split("-manual-")[0],
        run_ts=pd.Timestamp("2026-07-08T09:39:42"),
        mode="manual",
        status="ADVISORY_COMPLETE",
        context_artifact=context_path,
        candidates_artifact=candidates_path,
        risk_audit_artifact=risk_path,
        expressions_artifact=expressions_path,
    )


def test_quality_fail_returns_completed_status_and_withheld_quality(tmp_path: Path) -> None:
    run_id = "2026-07-08-manual-093942"
    manifest = _manifest_with_artifacts(
        tmp_path,
        run_id,
        context_rows=[{"symbol": "SPY", "trade_date": "2026-07-08"}],
        candidate_rows=[{"symbol": "AAPL"}],
        risk_rows=[
            {
                "symbol": "AAPL",
                "classification": "REJECTED_RR",
                "reject_reason": "spread_economics:insufficient_reward_risk",
                "candidate_loop_status": CandidateLoopStatus.HYDRATED.value,
                "hydration_status": "HYDRATED",
            }
        ],
    )

    result = build_run_advisory(tmp_path, manifest).run_advisory
    status = result["morning_regime_status"]

    assert status["woke"] is True
    assert status["quality_gate"] in {"NO_ACTION_QUALITY", "FAIL"}
    assert status["paper_action"] == "WITHHELD_QUALITY"
    assert status["selected_expression"] is None
    assert status["run_status"] == "ADVISORY_COMPLETE"


def test_missing_credentials_parks_hydration_but_completes(tmp_path: Path) -> None:
    run_id = "2026-07-08-manual-093942"
    manifest = _manifest_with_artifacts(
        tmp_path,
        run_id,
        context_rows=[{"symbol": "SPY", "trade_date": "2026-07-08"}],
        candidate_rows=[{"symbol": "TSLA"}],
        risk_rows=[
            {
                "symbol": "TSLA",
                "classification": CandidateLoopStatus.PARKED_DATA_GAP.value,
                "reject_reason": "credential_error:alpaca_missing_key_secret_pair",
                "candidate_loop_status": CandidateLoopStatus.PARKED_DATA_GAP.value,
                "hydration_status": "NO_CHAIN_AVAILABLE",
            }
        ],
    )

    result = build_run_advisory(tmp_path, manifest).run_advisory
    status = result["morning_regime_status"]

    assert status["hydration"] == "PARKED_CREDENTIAL_ERROR"
    assert status["paper_action"] == "WITHHELD_CREDENTIALS"
    assert status["run_status"] == "ADVISORY_COMPLETE"


def test_no_viable_structure_is_no_action_quality(tmp_path: Path) -> None:
    run_id = "2026-07-08-manual-093942"
    manifest = _manifest_with_artifacts(
        tmp_path,
        run_id,
        context_rows=[{"symbol": "SPY", "trade_date": "2026-07-08"}],
        candidate_rows=[{"symbol": "NVDA"}],
        risk_rows=[
            {
                "symbol": "NVDA",
                "classification": CandidateLoopStatus.NO_VIABLE_EXPRESSION.value,
                "reject_reason": "spread_economics:no_positive_max_profit_or_rr",
                "candidate_loop_status": CandidateLoopStatus.NO_VIABLE_EXPRESSION.value,
                "hydration_status": "NO_VIABLE_EXPRESSION",
            }
        ],
    )

    result = build_run_advisory(tmp_path, manifest).run_advisory
    status = result["morning_regime_status"]

    assert status["structure_build"] == "NO_VIABLE_STRUCTURE"
    assert status["paper_action"] == "WITHHELD_QUALITY"
    assert status["selected_expression"] is None


def test_watch_without_pass_is_withheld_quality(tmp_path: Path) -> None:
    run_id = "2026-07-08-manual-093942"
    manifest = _manifest_with_artifacts(
        tmp_path,
        run_id,
        context_rows=[{"symbol": "SPY", "trade_date": "2026-07-08"}],
        candidate_rows=[{"symbol": "MSFT"}],
        risk_rows=[
            {
                "symbol": "MSFT",
                "classification": CandidateLoopStatus.WATCH_EXPRESSION_AVAILABLE.value,
                "reject_reason": "operator_watch_review_required",
                "candidate_loop_status": CandidateLoopStatus.WATCH_EXPRESSION_AVAILABLE.value,
                "hydration_status": "HYDRATED",
            }
        ],
        expression_rows=[
            {
                "run_id": run_id,
                "symbol": "MSFT",
                "expression_id": "msft-watch",
                "expression_status": SpreadExpressionStatus.WATCH.value,
            }
        ],
    )

    result = build_run_advisory(tmp_path, manifest).run_advisory
    status = result["morning_regime_status"]

    assert status["quality_gate"] == "WATCH"
    assert status["paper_action"] == "WITHHELD_QUALITY"
    assert status["selected_expression"] is None
    assert "review" in " ".join(status["top_reasons"]).lower()


def test_pass_expression_sets_allowed_without_auto_submit(tmp_path: Path) -> None:
    run_id = "2026-07-08-manual-093942"
    manifest = _manifest_with_artifacts(
        tmp_path,
        run_id,
        context_rows=[{"symbol": "SPY", "trade_date": "2026-07-08"}],
        candidate_rows=[{"symbol": "GOOGL"}],
        risk_rows=[
            {
                "symbol": "GOOGL",
                "classification": "APPROVED_PAPER",
                "paper_approval_status": "APPROVED_FOR_PAPER_REVIEW",
                "reject_reason": "",
                "candidate_loop_status": CandidateLoopStatus.PRIMARY_EXPRESSION_SELECTED.value,
                "hydration_status": "HYDRATED",
            }
        ],
        expression_rows=[
            {
                "run_id": run_id,
                "symbol": "GOOGL",
                "expression_id": "googl-primary",
                "expression_status": SpreadExpressionStatus.PRIMARY.value,
            }
        ],
    )

    result = build_run_advisory(tmp_path, manifest).run_advisory
    status = result["morning_regime_status"]

    assert status["quality_gate"] == "PASS"
    assert status["paper_action"] == "ALLOWED"
    assert status["selected_expression"] == "googl-primary"
    assert result["paper_approval_allowed"] is True
