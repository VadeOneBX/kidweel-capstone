"""C2B reverse-VRP field normalization and symbol-context gate behavior."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from qops.backtest.spotgamma_replay_builder import build_replay_candidates, candidates_to_dataframe
from qops.ingest.spotgamma_loader import normalize_header_label
from qops.ingest.spotgamma_normalize import context_from_vrp_row
from qops.pipeline.alpaca_hydration_loop import _score_expression
from qops.risk.guard_runner import (
    enrich_morning_candidate_export,
    hydrate_morning_replay_candidates,
    run_risk_guard,
)
from qops.signals.classifier import compute_wall_distance_pct
from qops.strategy.dealer_expression_tier import wall_proximity_score
from qops.strategy.spread_candidate_generator import GeneratedSpreadCandidate
from qops.strategy.spread_math import SpreadMathEvaluation


def _reverse_vrp_series() -> pd.Series:
    return pd.Series(
        {
            "symbol": "ONDS",
            "current_price": 3.25,
            "hedge_wall": 3.5,
            "call_wall": 3.75,
            "put_wall": 3.0,
            "key_gamma_strike": 3.5,
            "key_delta_strike": 3.25,
            "one_month_iv": 0.62,
            "one_month_rv": 0.78,
            "iv_rank": 12.0,
            "source_file": "/data/spotgamma/raw/2026-06-18/reverse-vrp.xlsx",
        }
    )


def test_reverse_vrp_maps_wall_fields() -> None:
    ctx = context_from_vrp_row(_reverse_vrp_series(), profile="reverse_vrp", session_date="2026-06-18")
    candidates = build_replay_candidates([ctx])
    assert len(candidates) == 1
    row = candidates[0]
    assert row.current_price == 3.25
    assert row.call_wall == 3.75
    assert row.put_wall == 3.0
    assert row.hedge_wall == 3.5
    assert "key_gamma_strike=3.5" in ctx.notes
    assert "key_delta_strike=3.25" in ctx.notes


def test_reverse_vrp_maps_iv_rv_rank_fields() -> None:
    ctx = context_from_vrp_row(_reverse_vrp_series(), profile="reverse_vrp", session_date="2026-06-18")
    candidates = build_replay_candidates([ctx])
    row = candidates[0]
    assert row.one_month_iv == 0.62
    assert row.one_month_rv == 0.78
    assert row.iv_rank == 12.0


def test_reverse_vrp_derives_negative_vrp() -> None:
    ctx = context_from_vrp_row(_reverse_vrp_series(), profile="reverse_vrp", session_date="2026-06-18")
    assert ctx.vrp is not None
    assert round(ctx.vrp, 4) == round(0.62 - 0.78, 4)
    candidates = build_replay_candidates([ctx])
    assert candidates[0].vrp == ctx.vrp


def test_reverse_vrp_without_spy_context_does_not_skip_symbol_context(tmp_path: Path) -> None:
    ctx = context_from_vrp_row(_reverse_vrp_series(), profile="reverse_vrp", session_date="2026-06-18")
    candidates = build_replay_candidates([ctx])
    assert candidates[0].has_spy_context is False
    assert "spy_context" not in candidates[0].missing_fields

    candidate_df = enrich_morning_candidate_export(
        candidates_to_dataframe(candidates),
        run_id="run-rvrp",
    )
    candidate_df = hydrate_morning_replay_candidates(
        candidate_df,
        pd.DataFrame(columns=["symbol", "trade_date", "regime_label"]),
    )
    assert candidate_df.iloc[0]["context_gate_status"] == "CONTEXT_PASS"
    assert "spy_context" not in str(candidate_df.iloc[0]["missing_fields"])

    candidates_path = tmp_path / "candidates.csv"
    candidate_df.to_csv(candidates_path, index=False)
    audit = pd.read_csv(
        run_risk_guard(
            tmp_path,
            run_id="run-rvrp",
            candidates_artifact=str(candidates_path),
        ).risk_audit_artifact
    )
    assert audit.iloc[0]["classification"] == "HYDRATION_PENDING"
    assert "context_gate:spy_context" not in str(audit.iloc[0]["reject_reason"])


def test_reverse_vrp_fields_feed_wall_proximity_score() -> None:
    ctx = context_from_vrp_row(_reverse_vrp_series(), profile="reverse_vrp", session_date="2026-06-18")
    candidate_row = candidates_to_dataframe(build_replay_candidates([ctx])).iloc[0].to_dict()
    math = SpreadMathEvaluation(
        structure_type="BULL_CALL_SPREAD",
        spread_width=0.5,
        net_debit_or_credit=0.2,
        max_profit=0.3,
        max_loss=0.2,
        reward_risk=1.5,
        break_even=3.2,
        capital_at_risk=0.2,
        probability_of_profit=0.4,
        expected_value=0.05,
        rr_required=1.0,
        pass_reward_risk=True,
        pass_probability=True,
        pass_ev=True,
        ev_status="PASS",
        probability_status="PASS",
        passes_spread_math_gate=True,
        failure_reasons=(),
    )
    expr = GeneratedSpreadCandidate(
        structure_type="BULL_CALL_SPREAD",
        underlying_symbol="ONDS",
        trade_date="2026-06-18",
        expiration="2026-06-25",
        long_option_symbol="ONDS250625C00003000",
        short_option_symbol="ONDS250625C00003500",
        spread_width=0.5,
        net_debit_or_credit=0.2,
        reference_strike=3.0,
        probability_of_profit=0.4,
        math=math,
        candidate_pass=True,
        builder_succeeded=True,
        failure_reasons=(),
        provenance="test",
        greeks_provenance="test",
        long_greeks_source="alpaca_snapshot",
        long_greeks_confidence="high",
        short_greeks_source="alpaca_snapshot",
        short_greeks_confidence="high",
        pmp_for_gate=0.4,
        pmp_source="proxy",
        pmp_method="delta",
        pmp_proxy_status="PMP_PROXY_AVAILABLE",
        pmp_confidence="LOW",
        pmp_inputs_used=("delta",),
    )
    scored = _score_expression(expr, candidate_row=candidate_row)
    assert int(scored["wall_proximity_score"]) > 0
    short_strike = 3.5
    dist = compute_wall_distance_pct(short_strike, candidate_row["call_wall"])
    assert wall_proximity_score(dist) > 0


def test_reverse_vrp_header_normalization_maps_display_columns() -> None:
    from qops.ingest.spotgamma_loader import _REVERSE_VRP_HEADERS, _SCANNER_HEADERS

    assert _REVERSE_VRP_HEADERS[normalize_header_label("Call Wall")] == "call_wall"
    assert _REVERSE_VRP_HEADERS[normalize_header_label("1 M IV")] == "one_month_iv"
    assert _REVERSE_VRP_HEADERS[normalize_header_label("Gamma Ratio")] == "gamma_ratio"
    assert _REVERSE_VRP_HEADERS[normalize_header_label("Put/Call OI\xa0Ratio")] == "put_call_oi_ratio"
    assert _SCANNER_HEADERS == _REVERSE_VRP_HEADERS


def test_reverse_vrp_maps_gamma_ratio_when_present() -> None:
    series = _reverse_vrp_series()
    series["gamma_ratio"] = 1.8944
    series["delta_ratio"] = -1.6585
    series["put_call_oi_ratio"] = 0.853
    series["volume_ratio"] = 0.4344
    ctx = context_from_vrp_row(series, profile="reverse_vrp", session_date="2026-06-18")
    assert ctx.gamma_ratio == pytest.approx(1.8944)
    assert "gamma_ratio" not in ctx.missing_fields
    candidates = build_replay_candidates([ctx])
    assert candidates[0].gamma_ratio == pytest.approx(1.8944)
    assert candidates[0].delta_ratio == pytest.approx(-1.6585)
