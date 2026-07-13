"""SCHED-C1e morning risk guard candidate contract."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from qops.risk.guard_runner import (
    enrich_morning_candidate_export,
    hydrate_morning_replay_candidates,
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
                    "gamma_ratio_source": "squeeze",
                    "missing_fields": "",
                    "has_spy_context": True,
                    "source_profile": "squeeze",
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
    assert audit.iloc[0]["classification"] == "HYDRATION_PENDING"
    assert str(audit.iloc[0]["reject_reason"]).startswith("expression_hydration_pending:")
    summary = summarize_risk_audit(result.risk_audit_artifact)
    assert summary["rejected_missing_fields"] == 0
    assert summary["hydration_pending"] == 1
    assert summary["rejected_spread_economics"] == 0


def test_replay_audit_context_gap(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.csv"
    enrich_morning_candidate_export(
        pd.DataFrame(
            [
                {
                    "symbol": "AAPL",
                    "trade_date": "2026-06-18",
                    "gamma_ratio": None,
                    "gamma_ratio_source": "",
                    "missing_fields": "gamma_ratio",
                    "has_spy_context": True,
                    "source_profile": "squeeze",
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
    assert audit.iloc[0]["classification"] == "CONTEXT_INCOMPLETE"
    assert "context_gate:gamma_ratio" in str(audit.iloc[0]["reject_reason"])


def test_hydrate_gamma_join_and_source_absent() -> None:
    base = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "trade_date": "2026-06-18",
                "source_profile": "squeeze",
                "gamma_ratio": 1.2,
                "has_spy_context": True,
            },
            {
                "symbol": "AAPL",
                "trade_date": "2026-06-18",
                "source_profile": "vrp",
                "gamma_ratio": None,
                "has_spy_context": True,
            },
            {
                "symbol": "ZZZ",
                "trade_date": "2026-06-18",
                "source_profile": "reverse_vrp",
                "gamma_ratio": None,
                "has_spy_context": True,
            },
            {
                "symbol": "ETHA",
                "trade_date": "2026-06-18",
                "source_profile": "reverse_vrp",
                "gamma_ratio": 1.8944,
                "has_spy_context": True,
            },
        ]
    )
    context = pd.DataFrame(
        [{"symbol": "SPY", "trade_date": "2026-06-18", "regime_label": "SPY"}]
    )
    out = hydrate_morning_replay_candidates(base, context)
    squeeze_row = out.loc[out["source_profile"] == "squeeze"].iloc[0]
    vrp_row = out.loc[out["source_profile"] == "vrp"].iloc[0]
    zzz_row = out.loc[out["symbol"] == "ZZZ"].iloc[0]
    etha_row = out.loc[out["symbol"] == "ETHA"].iloc[0]
    assert squeeze_row["gamma_ratio_source"] == "squeeze"
    assert float(vrp_row["gamma_ratio"]) == 1.2
    assert vrp_row["gamma_ratio_source"] == "squeeze_join"
    assert zzz_row["gamma_ratio_source"] == "source_absent"
    assert zzz_row["missing_fields"] == ""
    assert float(etha_row["gamma_ratio"]) == pytest.approx(1.8944)
    assert etha_row["gamma_ratio_source"] == "reverse_vrp"
    assert str(squeeze_row["regime_label"]) == "SPY"


def test_source_absent_vrp_audit_uses_spread_economics_not_gamma_gate(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.csv"
    enrich_morning_candidate_export(
        pd.DataFrame(
            [
                {
                    "symbol": "ZZZ",
                    "trade_date": "2026-06-18",
                    "source_profile": "reverse_vrp",
                    "gamma_ratio": None,
                    "gamma_ratio_source": "source_absent",
                    "missing_fields": "",
                    "has_spy_context": True,
                }
            ]
        ),
        run_id="run-3",
    ).to_csv(candidates, index=False)

    result = run_risk_guard(tmp_path, run_id="run-3", candidates_artifact=str(candidates))
    audit = pd.read_csv(result.risk_audit_artifact)
    reason = str(audit.iloc[0]["reject_reason"])
    assert audit.iloc[0]["classification"] == "HYDRATION_PENDING"
    assert reason.startswith("expression_hydration_pending:")
    assert "context_gate:gamma_ratio" not in reason
