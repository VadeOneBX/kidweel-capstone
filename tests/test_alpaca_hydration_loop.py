"""STRUCT-C2A Alpaca hydration loop (read-only)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from qops.backtest.alpaca_greeks_layer import (
    AlpacaGreeksCandidateRow,
    check_alpaca_market_data_credentials,
    load_local_env,
    preflight_hydration_auth,
    try_create_option_client,
    validate_hydration_safety_env,
)
from qops.pipeline import alpaca_hydration_loop as hydration_module
from qops.pipeline.alpaca_hydration_loop import run_alpaca_expression_hydration
from qops.schemas.candidate_loop import CandidateLoopStatus, HydrationStatus, SpreadExpressionStatus
from qops.strategy.spread_candidate_generator import (
    ALL_STRUCTURES,
    StagedGreeksQuoteRow,
    quote_rows_from_greeks_candidates,
)


@pytest.fixture(autouse=True)
def _isolate_hydration_preflight_from_repo_dotenv(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    """Legacy hydration tests must not load the developer's repo `.env` into os.environ."""
    node_name = request.node.name
    if any(token in node_name for token in ("load_local", "unsafe", "missing_hydration")):
        return

    monkeypatch.setattr(
        "qops.pipeline.alpaca_hydration_loop.preflight_hydration_auth",
        lambda: None,
    )


def _quote_row(
    *,
    option_symbol: str,
    strike: float,
    option_type: str,
    bid: float,
    ask: float,
    underlying: str = "AAPL",
    pmp: float | None = 0.40,
) -> StagedGreeksQuoteRow:
    base = AlpacaGreeksCandidateRow(
        underlying_symbol=underlying,
        trade_date="2026-06-18",
        current_price=200.0,
        option_symbol=option_symbol,
        expiration="2026-06-25",
        strike=strike,
        option_type=option_type,
        bid=bid,
        ask=ask,
        mid=(bid + ask) / 2.0,
        latest_trade=None,
        delta=0.45,
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
        source_profile="test",
        has_spy_context=True,
        mode="paper_live",
        source="alpaca_paper_live_chain",
    )
    return StagedGreeksQuoteRow(quote=base, probability_of_profit=pmp)


def test_quote_rows_from_greeks_candidates_empty_produces_no_expressions(tmp_path: Path) -> None:
    assert quote_rows_from_greeks_candidates([]) == []
    df = pd.DataFrame(
        [{"symbol": "AAPL", "trade_date": "2026-06-18", "current_price": 200.0}]
    )
    out_path = tmp_path / "expressions.csv"

    def fake_stage(_specs, **kwargs):
        return [], True, None, []

    result = run_alpaca_expression_hydration(
        df,
        fetch=True,
        create_client_fn=lambda: (object(), None),
        stage_greeks_fn=fake_stage,
        expressions_output_path=out_path,
    )
    row = result.candidate_df.iloc[0]
    assert result.expression_count == 0
    assert result.expressions_df.empty
    assert row["candidate_loop_status"] in {
        CandidateLoopStatus.PARKED_DATA_GAP.value,
        CandidateLoopStatus.NO_VIABLE_EXPRESSION.value,
    }


def test_hydration_skips_fetch_without_credentials() -> None:
    df = pd.DataFrame([{"symbol": "AAPL", "trade_date": "2026-06-18", "current_price": 200.0}])
    result = run_alpaca_expression_hydration(
        df,
        fetch=True,
        create_client_fn=lambda: (None, "credential_error:test"),
    )
    row = result.candidate_df.iloc[0]
    assert row["candidate_loop_status"] == CandidateLoopStatus.PARKED_DATA_GAP.value
    assert row["hydration_status"] == HydrationStatus.PARKED_DATA_GAP.value
    assert "credential" in str(row["data_gap_reason"])


def test_hydration_selects_primary_expression() -> None:
    quotes = [
        _quote_row(option_symbol="C195", strike=195.0, option_type="call", bid=4.5, ask=4.6),
        _quote_row(option_symbol="C200", strike=200.0, option_type="call", bid=1.4, ask=1.5),
    ]
    greeks_rows = [q.quote for q in quotes]

    def fake_stage(_specs, **kwargs):
        return greeks_rows, True, None, []

    df = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "trade_date": "2026-06-18",
                "current_price": 200.0,
                "source_profile": "squeeze",
                "has_spy_context": True,
                "gamma_ratio": 1.3,
                "iv_rank": 25.0,
                "call_wall": 205.0,
            }
        ]
    )
    result = run_alpaca_expression_hydration(
        df,
        fetch=True,
        create_client_fn=lambda: (object(), None),
        stage_greeks_fn=fake_stage,
    )
    row = result.candidate_df.iloc[0]
    assert result.expression_count >= 1
    assert row["structure"] in ALL_STRUCTURES
    assert row["candidate_loop_status"] in {
        CandidateLoopStatus.PRIMARY_EXPRESSION_SELECTED.value,
        CandidateLoopStatus.ALTERNATES_AVAILABLE.value,
        CandidateLoopStatus.WATCH_EXPRESSION_AVAILABLE.value,
    }
    if row["candidate_loop_status"] == CandidateLoopStatus.PRIMARY_EXPRESSION_SELECTED.value:
        assert str(row["primary_expression_id"]).startswith("AAPL:")
        primary_rows = result.expressions_df[
            result.expressions_df["expression_id"] == row["primary_expression_id"]
        ]
        assert primary_rows.iloc[0]["expression_status"] == SpreadExpressionStatus.PRIMARY.value
    elif row["candidate_loop_status"] == CandidateLoopStatus.WATCH_EXPRESSION_AVAILABLE.value:
        assert not str(row.get("primary_expression_id", "")).strip()
        assert str(row.get("watch_expression_id", "")).startswith("AAPL:")
    assert row["dealer_gate_tier"] in {"A", "B", "C", "D", "E"}


def test_multi_expression_search_writes_artifact(tmp_path: Path) -> None:
    quotes = [
        _quote_row(option_symbol="C190", strike=190.0, option_type="call", bid=7.0, ask=7.1, pmp=0.38),
        _quote_row(option_symbol="C195", strike=195.0, option_type="call", bid=4.5, ask=4.6, pmp=0.40),
        _quote_row(option_symbol="C200", strike=200.0, option_type="call", bid=1.4, ask=1.5, pmp=0.42),
        _quote_row(option_symbol="C205", strike=205.0, option_type="call", bid=0.5, ask=0.6, pmp=0.44),
    ]
    greeks_rows = [q.quote for q in quotes]

    def fake_stage(_specs, **kwargs):
        return greeks_rows, True, None, []

    out_path = tmp_path / "alpaca_hydration_expressions.csv"
    df = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "trade_date": "2026-06-18",
                "current_price": 200.0,
                "gamma_ratio": 1.4,
                "iv_rank": 20.0,
                "call_wall": 205.0,
            }
        ]
    )
    result = run_alpaca_expression_hydration(
        df,
        fetch=True,
        create_client_fn=lambda: (object(), None),
        stage_greeks_fn=fake_stage,
        expressions_output_path=out_path,
    )
    assert out_path.is_file()
    expr_df = pd.read_csv(out_path)
    assert len(expr_df) >= 3
    widths = set(expr_df["width"].astype(float).unique())
    assert len(widths) >= 2
    assert (expr_df["expression_status"] == SpreadExpressionStatus.PRIMARY.value).sum() == 1
    assert (expr_df["expression_status"] == SpreadExpressionStatus.ALTERNATE.value).sum() >= 1


def test_candidate_preserved_when_first_expression_fails_tier() -> None:
    """Weak first pairing must not reject the candidate when a later expression is viable."""
    quotes = [
        _quote_row(option_symbol="C195", strike=195.0, option_type="call", bid=4.9, ask=5.0, pmp=0.55),
        _quote_row(option_symbol="C200", strike=200.0, option_type="call", bid=1.4, ask=1.5, pmp=0.40),
        _quote_row(option_symbol="C205", strike=205.0, option_type="call", bid=0.4, ask=0.5, pmp=0.35),
    ]
    greeks_rows = [q.quote for q in quotes]

    def fake_stage(_specs, **kwargs):
        return greeks_rows, True, None, []

    df = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "trade_date": "2026-06-18",
                "current_price": 200.0,
                "gamma_ratio": 1.2,
                "iv_rank": 30.0,
            }
        ]
    )
    result = run_alpaca_expression_hydration(
        df,
        fetch=True,
        create_client_fn=lambda: (object(), None),
        stage_greeks_fn=fake_stage,
    )
    row = result.candidate_df.iloc[0]
    assert row["candidate_loop_status"] != CandidateLoopStatus.NO_VIABLE_EXPRESSION.value
    assert int(row["expression_count"]) >= 2
    statuses = set(result.expressions_df["expression_status"].astype(str))
    assert SpreadExpressionStatus.FAILED_EXPRESSION.value in statuses or SpreadExpressionStatus.WATCH.value in statuses


def test_load_local_env_exposes_market_data_keys_for_client(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "APCA_API_KEY_ID=dotenv_key_id\nAPCA_API_SECRET_KEY=dotenv_secret\n",
        encoding="utf-8",
    )
    with patch.dict(os.environ, {}, clear=True):
        assert load_local_env(env_path=env_file) is True
        check = check_alpaca_market_data_credentials()
        assert check.credential_status == "READY"
        assert check.env_pair_label == "APCA_*"
        with patch(
            "alpaca.data.historical.option.OptionHistoricalDataClient",
        ) as mock_client_cls, patch(
            "qops.backtest.alpaca_greeks_layer.load_local_env",
            side_effect=lambda *, env_path=None: load_local_env(env_path=env_file)
            if env_path is not None
            else False,
        ):
            mock_client_cls.return_value = object()
            client, err = try_create_option_client()
        assert err is None
        assert client is not None
        mock_client_cls.assert_called_once_with(
            api_key="dotenv_key_id",
            secret_key="dotenv_secret",
            raw_data=True,
        )


@pytest.mark.parametrize("unsafe_value", ["false", "0", "no", "off"])
def test_unsafe_hydration_env_flag_blocks_preflight(unsafe_value: str) -> None:
    with patch.dict(os.environ, {"NO_SUBMIT": unsafe_value}, clear=True):
        assert validate_hydration_safety_env() == "preflight_error:unsafe_env_flag:NO_SUBMIT"


def test_missing_hydration_safety_flags_allow_preflight() -> None:
    with patch.dict(os.environ, {}, clear=True):
        assert validate_hydration_safety_env() is None
    with patch.dict(os.environ, {}, clear=True), patch(
        "qops.backtest.alpaca_greeks_layer.load_local_env",
        return_value=False,
    ):
        assert preflight_hydration_auth() is None


def test_unsafe_flag_blocks_hydration_before_client() -> None:
    df = pd.DataFrame([{"symbol": "AAPL", "trade_date": "2026-06-18", "current_price": 200.0}])
    create_calls: list[object] = []

    def tracking_create() -> tuple[object | None, str | None]:
        create_calls.append(object())
        return object(), None

    with patch.dict(os.environ, {"DRY_RUN": "false"}, clear=True), patch(
        "qops.backtest.alpaca_greeks_layer.load_local_env",
        return_value=False,
    ):
        result = run_alpaca_expression_hydration(
            df,
            fetch=True,
            create_client_fn=tracking_create,
        )
    assert create_calls == []
    row = result.candidate_df.iloc[0]
    assert "preflight_error" in str(result.fetch_skip_reason)
    assert row["hydration_status"] == HydrationStatus.PARKED_DATA_GAP.value


def test_hydration_module_has_no_paper_submit_path() -> None:
    source = Path(hydration_module.__file__).read_text(encoding="utf-8")
    assert "submit_paper" not in source
    assert "run_paper_payload_transport" not in source
