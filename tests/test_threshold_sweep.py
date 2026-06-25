"""THRESH-C1 threshold sweep tests (offline)."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pandas as pd

from qops.analysis.threshold_sweep import (
    enrich_spread_candidates,
    run_threshold_sweep,
)
from qops.backtest.alpaca_greeks_layer import AlpacaGreeksCandidateRow, greeks_candidates_to_dataframe
from qops.execution.paper_payload_candidate import PaperApprovalInputRow
from qops.schemas.playbook import AllowedPlaybook
from qops.strategy.spread_candidate_generator import (
    StagedGreeksQuoteRow,
    generate_spread_candidates,
    spread_candidates_to_dataframe,
)


def _greeks(
    option_symbol: str,
    strike: float,
    option_type: str,
    bid: float,
    ask: float,
    delta: float,
    source_profile: str = "squeeze",
) -> AlpacaGreeksCandidateRow:
    return AlpacaGreeksCandidateRow(
        underlying_symbol="SPY",
        trade_date="2026-06-13",
        current_price=425.0,
        option_symbol=option_symbol,
        expiration="2026-06-20",
        strike=strike,
        option_type=option_type,
        bid=bid,
        ask=ask,
        mid=(bid + ask) / 2.0,
        latest_trade=None,
        delta=delta,
        gamma=0.02,
        theta=-0.05,
        vega=0.1,
        rho=0.01,
        implied_volatility=0.2,
        greeks_source="alpaca_snapshot",
        greeks_status="AVAILABLE",
        greeks_confidence="high",
        volatility_is_proxy=False,
        provenance="test",
        blueprint_provenance="test",
        source_profile=source_profile,
        has_spy_context=True,
    )


def _write_spreads(tmp_path: Path, *, rr: float, ev: float | None, pmp: float, candidate_pass: bool) -> None:
    rows = [
        StagedGreeksQuoteRow(
            quote=_greeks("L", 420.0, "call", 1.45, 1.50, 0.55),
            probability_of_profit=None,
        ),
        StagedGreeksQuoteRow(
            quote=_greeks("S", 425.0, "call", 0.45, 0.50, 0.35, source_profile="squeeze"),
            probability_of_profit=pmp,
        ),
    ]
    greeks_candidates_to_dataframe([r.quote for r in rows]).to_csv(tmp_path / "greeks.csv", index=False)
    candidates = generate_spread_candidates(rows, structures=[AllowedPlaybook.BULL_CALL_SPREAD.value])
    df = spread_candidates_to_dataframe(candidates)
    df["reward_risk"] = rr
    if ev is not None:
        df["expected_value"] = ev
    df["candidate_pass"] = candidate_pass
    df.to_csv(tmp_path / "spreads.csv", index=False)


def _spread_row_csv(
    tmp_path: Path,
    *,
    rr: float,
    pmp: float,
    ev: float,
    candidate_pass: bool,
    failure_reasons: str = "",
) -> None:
    pd.DataFrame(
        [
            {
                "structure_type": "BULL_CALL_SPREAD",
                "underlying_symbol": "SPY",
                "trade_date": "2026-06-13",
                "expiration": "2026-06-20",
                "long_option_symbol": "L",
                "short_option_symbol": "S",
                "spread_width": 5.0,
                "net_debit_or_credit": 1.0,
                "pmp_for_gate": pmp,
                "pmp_source": "vendor",
                "pmp_confidence": "HIGH",
                "max_profit": 4.0,
                "max_loss": 1.0,
                "reward_risk": rr,
                "expected_value": ev,
                "break_even": 421.0,
                "capital_at_risk": 1.0,
                "passes_spread_math_gate": True,
                "probability_status": "PASS",
                "ev_status": "PASS" if ev > 0 else "WATCH",
                "candidate_pass": candidate_pass,
                "failure_reasons": failure_reasons,
                "provenance": "test",
            }
        ]
    ).to_csv(tmp_path / "spreads.csv", index=False)


def test_rr_gte_2_filter(tmp_path: Path) -> None:
    _spread_row_csv(tmp_path, rr=2.5, pmp=0.55, ev=0.5, candidate_pass=True)
    _, results = run_threshold_sweep(
        spreads_path=tmp_path / "spreads.csv",
        greeks_path=tmp_path / "x.csv",
    )
    rr2 = next(r for r in results if r.scenario_name == "rr_gte_2_00")
    assert rr2.pass_count == 1
    rr3 = next(r for r in results if r.scenario_name == "rr_gte_3_00")
    assert rr3.pass_count == 0


def test_ev_gte_0_filter(tmp_path: Path) -> None:
    _spread_row_csv(tmp_path, rr=1.5, pmp=0.55, ev=0.01, candidate_pass=True)
    _, results = run_threshold_sweep(spreads_path=tmp_path / "spreads.csv", greeks_path=tmp_path / "x.csv")
    ev0 = next(r for r in results if r.scenario_name == "ev_gte_0_00")
    assert ev0.pass_count == 1
    ev25 = next(r for r in results if r.scenario_name == "ev_gte_0_25")
    assert ev25.pass_count == 0


def test_bid_ask_lte_050_filter(tmp_path: Path) -> None:
    _write_spreads(tmp_path, rr=2.0, ev=0.5, pmp=0.55, candidate_pass=True)
    _, results = run_threshold_sweep(
        spreads_path=tmp_path / "spreads.csv",
        greeks_path=tmp_path / "greeks.csv",
    )
    ba = next(r for r in results if r.scenario_name == "bid_ask_spread_pct_lte_0_50")
    assert ba.pass_count >= 1


def test_combined_ev_rr_bid_ask(tmp_path: Path) -> None:
    _write_spreads(tmp_path, rr=2.5, ev=0.5, pmp=0.55, candidate_pass=True)
    _, results = run_threshold_sweep(
        spreads_path=tmp_path / "spreads.csv",
        greeks_path=tmp_path / "greeks.csv",
    )
    combo = next(
        r for r in results if r.scenario_name == "ev_gte_0_and_rr_gte_2_00_and_bid_ask_spread_pct_lte_0_50"
    )
    assert combo.pass_count >= 1


def test_missing_bid_ask_not_passed_for_ba_scenario(tmp_path: Path) -> None:
    _spread_row_csv(tmp_path, rr=2.5, pmp=0.55, ev=0.5, candidate_pass=True)
    _, results = run_threshold_sweep(spreads_path=tmp_path / "spreads.csv", greeks_path=tmp_path / "x.csv")
    ba = next(r for r in results if r.scenario_name == "bid_ask_spread_pct_lte_0_50")
    assert ba.pass_count == 0
    assert ba.missing_field_counts.get("missing_bid_ask_spread_pct", 0) >= 1


def test_missing_pmp_not_passed(tmp_path: Path) -> None:
    pd.DataFrame(
        [
            {
                "structure_type": "BULL_CALL_SPREAD",
                "underlying_symbol": "SPY",
                "trade_date": "2026-06-13",
                "expiration": "2026-06-20",
                "long_option_symbol": "L",
                "short_option_symbol": "S",
                "spread_width": 5.0,
                "net_debit_or_credit": 1.0,
                "pmp_for_gate": None,
                "pmp_source": "missing",
                "pmp_confidence": "MISSING",
                "max_profit": 4.0,
                "max_loss": 1.0,
                "reward_risk": 3.0,
                "break_even": 421.0,
                "capital_at_risk": 1.0,
                "passes_spread_math_gate": True,
                "probability_status": "INCOMPLETE",
                "ev_status": "INCOMPLETE",
                "candidate_pass": False,
                "failure_reasons": "missing_probability_of_profit",
                "provenance": "test",
            }
        ]
    ).to_csv(tmp_path / "spreads.csv", index=False)
    rows, results = run_threshold_sweep(spreads_path=tmp_path / "spreads.csv", greeks_path=tmp_path / "x.csv")
    rr2 = next(r for r in results if r.scenario_name == "rr_gte_2_00")
    assert rr2.pass_count == 0
    assert rows[0].pmp is None


def test_approved_count_from_approval_file_only(tmp_path: Path) -> None:
    _spread_row_csv(tmp_path, rr=2.5, pmp=0.55, ev=0.5, candidate_pass=True)
    approval = PaperApprovalInputRow(
        approval_id="a1",
        symbol="SPY",
        trade_date="2026-06-13",
        structure_type="BULL_CALL_SPREAD",
        long_leg_symbol="L",
        short_leg_symbol="S",
        expiration="2026-06-20",
        net_debit_or_credit=1.0,
        max_profit=4.0,
        max_loss=1.0,
        reward_risk=2.5,
        pmp=0.55,
        pmp_source="vendor",
        pmp_confidence="HIGH",
        expected_value=0.5,
        approval_status="APPROVED_FOR_PAPER_REVIEW",
        failure_reasons="",
        suggested_contract_qty=1,
        provenance="test",
    )
    pd.DataFrame([asdict(approval)]).to_csv(tmp_path / "approvals.csv", index=False)
    _, results = run_threshold_sweep(
        spreads_path=tmp_path / "spreads.csv",
        greeks_path=tmp_path / "x.csv",
        approvals_path=tmp_path / "approvals.csv",
    )
    rr2 = next(r for r in results if r.scenario_name == "rr_gte_2_00")
    assert rr2.approved_count == 1


def test_advisory_group_split(tmp_path: Path) -> None:
    _write_spreads(tmp_path, rr=2.5, ev=0.5, pmp=0.55, candidate_pass=True)
    rows = enrich_spread_candidates(tmp_path / "spreads.csv", greeks_path=tmp_path / "greeks.csv")
    assert rows[0].advisory_group == "SQUEEZE_CANDIDATES"
    _, results = run_threshold_sweep(
        spreads_path=tmp_path / "spreads.csv",
        greeks_path=tmp_path / "greeks.csv",
    )
    rr2 = next(r for r in results if r.scenario_name == "rr_gte_2_00")
    assert rr2.by_advisory_group.get("SQUEEZE_CANDIDATES", 0) >= 1


def test_no_broker_in_threshold_sweep_module() -> None:
    source = Path("src/qops/analysis/threshold_sweep.py").read_text(encoding="utf-8")
    assert "alpaca_paper_bridge" not in source
    assert "submit_paper" not in source
    assert "mcp_gate" not in source


def test_baseline_uses_candidate_pass(tmp_path: Path) -> None:
    _spread_row_csv(tmp_path, rr=1.2, pmp=0.55, ev=0.1, candidate_pass=False)
    _, results = run_threshold_sweep(spreads_path=tmp_path / "spreads.csv", greeks_path=tmp_path / "x.csv")
    baseline = next(r for r in results if r.scenario_name == "baseline")
    assert baseline.pass_count == 0
    assert baseline.candidate_pass_count == 0
