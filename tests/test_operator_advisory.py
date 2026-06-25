"""ADVISORY-VOICE-C1 operator advisory generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from qops.advisory.operator_advisory import generate_operator_advisory

_ACCEPTANCE_RUN = "2026-06-23-manual-091340"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.mark.skipif(
    not (_repo_root() / f"data/processed/risk/{_ACCEPTANCE_RUN}_risk_audit.csv").is_file(),
    reason="acceptance run artifacts not present locally",
)
def test_acceptance_run_2026_06_23_manual_091340() -> None:
    base = _repo_root()
    result = generate_operator_advisory(base, _ACCEPTANCE_RUN)
    path = Path(result.operator_advisory_artifact)
    assert path.is_file()
    text = path.read_text(encoding="utf-8").lower()
    assert "21" in text and "200" in text
    assert "ibit" in text
    assert "primary expression" in text or "primary expression note" in text
    assert "watch" in text
    assert "not a broken candidate" in text
    assert "nio" in text or "no-viable" in text
    assert "rejection is evidence" in text
    assert "llm recommends" not in text
    assert "ai selected" not in text
    assert "bad trade" not in text


def test_operator_advisory_synthetic_minimal(tmp_path: Path) -> None:
    run_id = "test-voice-run"
    (tmp_path / "data/processed/context").mkdir(parents=True)
    (tmp_path / "data/processed/candidates").mkdir(parents=True)
    (tmp_path / "data/processed/risk").mkdir(parents=True)

    import pandas as pd

    pd.DataFrame([{"symbol": "SPY"}]).to_csv(
        tmp_path / f"data/processed/context/{run_id}_context.csv", index=False
    )
    pd.DataFrame(
        [
            {
                "symbol": "SOFI",
                "candidate_loop_status": "WATCH_EXPRESSION_AVAILABLE",
            }
        ]
    ).to_csv(tmp_path / f"data/processed/candidates/{run_id}_candidates.csv", index=False)
    pd.DataFrame(
        [
            {
                "run_id": run_id,
                "symbol": "IBIT",
                "expression_status": "PRIMARY",
                "structure": "BULL_CALL_SPREAD",
                "expiration": "2026-06-26",
                "dte": 3,
                "long_strike": 36.5,
                "short_strike": 37.0,
                "debit": 0.21,
                "max_profit": 0.29,
                "max_loss": 0.21,
                "rr_actual": 1.38,
                "pmp": 0.25,
                "dealer_gate_tier": "A",
                "dealer_weighted_score": 10,
                "bid_ask_quality": "PASS",
                "expression_reason": "primary expression under dealer-weighted tier",
            }
        ]
    ).to_csv(
        tmp_path / f"data/processed/{run_id}_alpaca_hydration_expressions.csv",
        index=False,
    )
    pd.DataFrame(
        [
            {
                "symbol": "SOFI",
                "classification": "WATCH_EXPRESSION_AVAILABLE",
            },
            {
                "symbol": "NIO",
                "classification": "NO_VIABLE_EXPRESSION",
                "reject_reason": "expression_search_exhausted:no_viable_expression",
            },
        ]
    ).to_csv(tmp_path / f"data/processed/risk/{run_id}_risk_audit.csv", index=False)

    result = generate_operator_advisory(tmp_path, run_id)
    body = Path(result.operator_advisory_artifact).read_text(encoding="utf-8")
    assert "SOFI" in body
    assert "operator review candidate" in body
    assert "NIO" in body
    assert "clean reject" in body.lower() or "no paper-tradable" in body.lower()
    assert "IBIT" in body
    assert "$21" in body or "$29" in body
    assert "%" in body
    assert "Capstone evidence" in body
