"""BT-C3 canonical evidence refresh tests (offline, no broker)."""

from __future__ import annotations

import math
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from qops.backtest.alpaca_greeks_layer import AlpacaGreeksCandidateRow, greeks_candidates_to_dataframe
from qops.backtest.canonical_refresh import (
    CanonicalRefreshPaths,
    advisory_group_from_profile,
    evidence_rows_from_fixtures,
    run_canonical_backtest_refresh,
    summarize_canonical_refresh,
)
from qops.backtest.replay_context import ReplayContext, validate_replay_context
from qops.backtest.spotgamma_replay_builder import ReplayCandidateRow, candidates_to_dataframe
from qops.execution.paper_payload_candidate import PaperApprovalInputRow
from qops.schemas.environment import (
    DirectionalBias,
    IVState,
    RegimeLabel,
    SkewState,
    WallState,
)
from qops.schemas.playbook import AllowedPlaybook
from qops.schemas.risk import TradeEvaluation
from qops.schemas.structure import TradeStructureCandidate
from qops.strategy.spread_candidate_generator import (
    StagedGreeksQuoteRow,
    generate_spread_candidates,
    spread_candidates_to_dataframe,
)


def _greeks_row(
    *,
    option_symbol: str,
    strike: float,
    option_type: str,
    bid: float,
    ask: float,
    delta: float,
    source_profile: str = "squeeze",
    mode: str = "historical_replay",
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
        mode=mode,
        source="alpaca_greeks_c1_staging",
    )


def _write_pipeline_csvs(tmp_path: Path, *, pmp: float | None = 0.55) -> None:
    rows = [
        StagedGreeksQuoteRow(
            quote=_greeks_row(
                option_symbol="SPY260620C00420000",
                strike=420.0,
                option_type="call",
                bid=1.45,
                ask=1.50,
                delta=0.55,
                source_profile="squeeze",
            ),
            probability_of_profit=None,
        ),
        StagedGreeksQuoteRow(
            quote=_greeks_row(
                option_symbol="SPY260620C00425000",
                strike=425.0,
                option_type="call",
                bid=0.45,
                ask=0.50,
                delta=0.35,
                source_profile="squeeze",
            ),
            probability_of_profit=pmp,
        ),
    ]
    candidates = generate_spread_candidates(
        rows, structures=[AllowedPlaybook.BULL_CALL_SPREAD.value]
    )
    assert candidates
    greeks_candidates_to_dataframe([r.quote for r in rows]).to_csv(
        tmp_path / "greeks.csv", index=False
    )
    spread_candidates_to_dataframe(candidates).to_csv(tmp_path / "spreads.csv", index=False)


def test_advisory_group_mapping() -> None:
    assert advisory_group_from_profile("squeeze") == "SQUEEZE_CANDIDATES"
    assert advisory_group_from_profile("vrp") == "VOLATILITY_RISK_PREMIUM"
    assert advisory_group_from_profile("reverse_vrp") == "REVERSE_RISK_PREMIUM"
    assert advisory_group_from_profile("") == "UNKNOWN"


def test_evidence_class_separation(tmp_path: Path) -> None:
    _write_pipeline_csvs(tmp_path)
    sg = ReplayCandidateRow(
        symbol="SPY",
        trade_date="2026-06-13",
        source_profile="vrp",
        source_file="x.csv",
        current_price=425.0,
        gamma_ratio=None,
        delta_ratio=None,
        put_call_oi_ratio=None,
        volume_ratio=None,
        iv_rank=None,
        vrp=None,
        one_month_iv=None,
        one_month_rv=None,
        skew=None,
        ne_skew=None,
        options_impact=None,
        options_implied_move=None,
        call_wall=None,
        put_wall=None,
        hedge_wall=None,
        spy_gamma_ratio=None,
        spy_delta_ratio=None,
        spy_put_call_oi_ratio=None,
        spy_volume_ratio=None,
        spy_vrp=None,
        spy_one_month_iv=None,
        spy_one_month_rv=None,
        spy_iv_rank=None,
        spy_skew=None,
        spy_ne_skew=None,
        spy_call_wall=None,
        spy_put_wall=None,
        spy_hedge_wall=None,
        candidate_reason="vrp_profile_candidate",
        missing_fields="",
        has_spy_context=True,
    )
    candidates_to_dataframe([sg]).to_csv(tmp_path / "sg.csv", index=False)

    paths = CanonicalRefreshPaths(
        spreads=tmp_path / "spreads.csv",
        approvals=tmp_path / "missing_approvals.csv",
        payloads=tmp_path / "missing_payloads.csv",
        greeks=tmp_path / "greeks.csv",
        sg=tmp_path / "sg.csv",
    )
    evidence, summary = run_canonical_backtest_refresh(paths, derive_spreads_if_missing=False)
    classes = {r.evidence_class for r in evidence}
    assert "STRUCTURE_EVIDENCE_ONLY" in classes
    assert "INCOMPLETE_MISSING_DATA" in classes
    assert summary["per_class_summaries"]["STRUCTURE_EVIDENCE_ONLY"]["row_count"] >= 1
    assert summary["per_class_summaries"]["INCOMPLETE_MISSING_DATA"]["row_count"] == 1


def test_spread_delta_ranking_for_squeeze(tmp_path: Path) -> None:
    _write_pipeline_csvs(tmp_path)
    paths = CanonicalRefreshPaths(
        spreads=tmp_path / "spreads.csv",
        approvals=tmp_path / "x.csv",
        payloads=tmp_path / "x.csv",
        greeks=tmp_path / "greeks.csv",
        sg=tmp_path / "x.csv",
    )
    _, summary = run_canonical_backtest_refresh(paths, derive_spreads_if_missing=False)
    tops = summary["top_squeeze_candidates_by_spread_delta"]
    assert tops
    assert math.isclose(tops[0]["spread_delta"], 0.2, rel_tol=0.0, abs_tol=1e-9)


def test_missing_pmp_and_no_fabricated_pnl(tmp_path: Path) -> None:
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
                "reward_risk": 4.0,
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
    paths = CanonicalRefreshPaths(
        spreads=tmp_path / "spreads.csv",
        approvals=tmp_path / "x.csv",
        payloads=tmp_path / "x.csv",
        greeks=tmp_path / "x.csv",
        sg=tmp_path / "x.csv",
    )
    evidence, summary = run_canonical_backtest_refresh(paths, derive_spreads_if_missing=False)
    spread_rows = [r for r in evidence if r.row_kind == "spread_candidate"]
    assert spread_rows
    assert spread_rows[0].missing_pmp
    assert not spread_rows[0].candidate_pass
    assert spread_rows[0].realized_pnl is None
    assert summary["missing_pmp_count"] >= 1


def test_missing_exit_handling(tmp_path: Path) -> None:
    _write_pipeline_csvs(tmp_path)
    paths = CanonicalRefreshPaths(
        spreads=tmp_path / "spreads.csv",
        approvals=tmp_path / "x.csv",
        payloads=tmp_path / "x.csv",
        greeks=tmp_path / "greeks.csv",
        sg=tmp_path / "x.csv",
    )
    evidence, summary = run_canonical_backtest_refresh(paths, derive_spreads_if_missing=False)
    spread_rows = [r for r in evidence if r.row_kind == "spread_candidate"]
    assert all(r.missing_exit for r in spread_rows)
    assert summary["missing_exit_count"] >= 1


def test_rr_pmp_summary_counts_fail_reason(tmp_path: Path) -> None:
    df = pd.DataFrame(
        [
            {
                "structure_type": "BULL_CALL_SPREAD",
                "underlying_symbol": "SPY",
                "trade_date": "2026-06-13",
                "expiration": "2026-06-20",
                "long_option_symbol": "L",
                "short_option_symbol": "S",
                "spread_width": 5.0,
                "net_debit_or_credit": 2.0,
                "pmp_for_gate": 0.55,
                "pmp_source": "vendor",
                "pmp_confidence": "HIGH",
                "max_profit": 3.0,
                "max_loss": 2.0,
                "reward_risk": 1.0,
                "break_even": 422.0,
                "capital_at_risk": 2.0,
                "passes_spread_math_gate": True,
                "probability_status": "PASS",
                "ev_status": "WATCH",
                "candidate_pass": False,
                "failure_reasons": "insufficient_reward_risk_for_probability",
                "provenance": "test",
            }
        ]
    )
    df.to_csv(tmp_path / "spreads.csv", index=False)
    paths = CanonicalRefreshPaths(
        spreads=tmp_path / "spreads.csv",
        approvals=tmp_path / "x.csv",
        payloads=tmp_path / "x.csv",
        greeks=tmp_path / "x.csv",
        sg=tmp_path / "x.csv",
    )
    _, summary = run_canonical_backtest_refresh(paths, derive_spreads_if_missing=False)
    assert summary["rr_pmp_summary"]["insufficient_reward_risk_for_pmp_count"] == 1
    assert summary["candidates_passing_pmp_rr"] == 0


def test_fixture_evidence_not_historical_replay() -> None:
    structure = TradeStructureCandidate(
        symbol="SPY",
        structure_type="bullish_debit_spread",
        expiry="2024-06-21",
        width=5.0,
        debit_or_credit=1.20,
        max_profit=3.8,
        max_loss=1.2,
        rr_actual=3.16,
        regime_label=RegimeLabel.SQUEEZE_UP,
        confidence=7,
        gamma_ratio=0.42,
        iv_state=IVState.MID_VOL,
        skew_state=SkewState.NEUTRAL,
        wall_state=WallState.BETWEEN_WALLS,
        directional_bias=DirectionalBias.BULLISH_BIAS,
        allowed_playbook=AllowedPlaybook.BULL_CALL_SPREAD,
        structure_reason="test",
    )
    evaluation = TradeEvaluation(
        symbol="SPY",
        playbook="BULL_CALL_SPREAD",
        pmp=0.58,
        rr_required=1.35,
        rr_actual=3.16,
        max_profit=3.8,
        max_loss=1.2,
        tp_rule="TP_80",
        sl_rule="STOP",
        time_exit_rule="TIME_EXIT",
        environment_fit=True,
        pass_rr=True,
        pass_risk=True,
        approved=True,
        approval_reason="test",
    )
    ctx = ReplayContext(
        symbol="SPY",
        playbook="BULL_CALL_SPREAD",
        structure=structure,
        evaluation=evaluation,
        entry_date="2024-01-08",
        exit_date="2024-01-15",
        dte_at_entry=14,
        realized_pnl=110.0,
        exit_reason="TP_80",
        environment_label="SQUEEZE_UP_CHEAP_VOL",
    )
    validate_replay_context(ctx)
    rows = evidence_rows_from_fixtures([("seeded_sanity", ctx)])
    assert rows[0].evidence_class == "FIXTURE_EVIDENCE"
    assert rows[0].pnl_source == "fixture_declared"
    summary = summarize_canonical_refresh(
        all_rows=rows,
        spread_input_count=0,
        spread_derived=False,
        approval_rows=[],
        payload_ready_count=0,
        inputs_present={},
        limitations=[],
    )
    assert summary["trades_with_real_exit_pnl"] == 0
    assert summary["evidence_rows_by_class"]["FIXTURE_EVIDENCE"] == 1


def test_no_broker_imports_in_canonical_refresh_module() -> None:
    source = Path("src/qops/backtest/canonical_refresh.py").read_text(encoding="utf-8")
    assert "alpaca_paper_bridge" not in source
    assert "mcp_gate" not in source
    assert "submit_paper" not in source


def test_historical_exit_pnl_when_declared(tmp_path: Path) -> None:
    _write_pipeline_csvs(tmp_path)
    spreads = pd.read_csv(tmp_path / "spreads.csv")
    spreads["realized_pnl"] = 42.0
    spreads.to_csv(tmp_path / "spreads.csv", index=False)
    paths = CanonicalRefreshPaths(
        spreads=tmp_path / "spreads.csv",
        approvals=tmp_path / "x.csv",
        payloads=tmp_path / "x.csv",
        greeks=tmp_path / "greeks.csv",
        sg=tmp_path / "x.csv",
    )
    evidence, summary = run_canonical_backtest_refresh(paths, derive_spreads_if_missing=False)
    hist = [r for r in evidence if r.evidence_class == "HISTORICAL_REPLAY_EVIDENCE"]
    assert hist
    assert hist[0].realized_pnl == 42.0
    assert summary["trades_with_real_exit_pnl"] == 1


def test_approval_ready_count_from_csv(tmp_path: Path) -> None:
    _write_pipeline_csvs(tmp_path)
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
        reward_risk=4.0,
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
    paths = CanonicalRefreshPaths(
        spreads=tmp_path / "spreads.csv",
        approvals=tmp_path / "approvals.csv",
        payloads=tmp_path / "x.csv",
        greeks=tmp_path / "greeks.csv",
        sg=tmp_path / "x.csv",
    )
    _, summary = run_canonical_backtest_refresh(paths, derive_spreads_if_missing=False)
    assert summary["approval_ready_count"] == 1
