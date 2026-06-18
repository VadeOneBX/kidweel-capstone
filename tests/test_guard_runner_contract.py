"""SCHED-C1e morning risk guard candidate contract."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from qops.risk.guard_runner import (
    enrich_morning_candidate_export,
    run_risk_guard,
    spread_contract_gaps,
    summarize_risk_audit,
)


def test_spread_contract_gaps_lists_missing_economics() -> None:
    row = pd.Series(
        {
            "symbol": "AAPL",
            "structure": "",
            "expiration": "",
            "pmp": None,
        }
    )
    gaps = spread_contract_gaps(row)
    assert "structure" in gaps
    assert "expiration" in gaps
    assert "pmp" in gaps


def test_enrich_morning_candidate_export_adds_contract_columns() -> None:
    base = pd.DataFrame([{"symbol": "AAPL", "trade_date": "2026-06-18", "gamma_ratio": 1.0}])
    out = enrich_morning_candidate_export(base, run_id="2026-06-18-manual-test")
    assert out.iloc[0]["run_id"] == "2026-06-18-manual-test"
    assert out.iloc[0]["underlying"] == "AAPL"
    assert out.iloc[0]["structure_bias"] == "SKIP"
    assert "structure" in out.columns
    assert "pmp" in out.columns


def test_replay_audit_classifies_spread_economics(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.csv"
    context = tmp_path / "context.csv"
    enrich_morning_candidate_export(
        pd.DataFrame(
            [
                {
                    "symbol": "AAPL",
                    "trade_date": "2026-06-18",
                    "gamma_ratio": 1.1,
                    "missing_fields": "",
                    "has_spy_context": True,
                }
            ]
        ),
        run_id="run-1",
    ).to_csv(candidates, index=False)
    pd.DataFrame(
        [{"symbol": "SPY", "trade_date": "2026-06-18", "regime_label": "NEUTRAL"}]
    ).to_csv(context, index=False)

    result = run_risk_guard(
        tmp_path,
        run_id="run-1",
        candidates_artifact=str(candidates),
        context_artifact=str(context),
    )
    audit = pd.read_csv(result.risk_audit_artifact)
    assert audit.iloc[0]["classification"] == "REJECTED_MISSING_FIELDS"
    assert str(audit.iloc[0]["reject_reason"]).startswith("spread_economics:")
    summary = summarize_risk_audit(result.risk_audit_artifact)
    assert summary["rejected_missing_fields"] == 1
    assert summary["rejected_spread_economics"] == 1


def test_replay_audit_context_gap(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.csv"
    enrich_morning_candidate_export(
        pd.DataFrame(
            [
                {
                    "symbol": "AAPL",
                    "trade_date": "2026-06-18",
                    "gamma_ratio": None,
                    "missing_fields": "gamma_ratio",
                    "has_spy_context": True,
                }
            ]
        ),
        run_id="run-2",
    ).to_csv(candidates, index=False)

    result = run_risk_guard(
        tmp_path,
        run_id="run-2",
        candidates_artifact=str(candidates),
    )
    audit = pd.read_csv(result.risk_audit_artifact)
    assert audit.iloc[0]["classification"] == "REJECTED_MISSING_FIELDS"
    assert "context_gate:gamma_ratio" in str(audit.iloc[0]["reject_reason"])
