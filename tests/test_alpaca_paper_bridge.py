"""MCP-C12A: Alpaca paper transport bridge."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from examples.submit_paper_payload_candidates import main as submit_main
from qops.execution.alpaca_paper_bridge import (
    CANONICAL_PAPER_BASE_URL,
    PROFILE_CLI_SUBMIT_NOT_IMPLEMENTED,
    AlpacaPaperCredentials,
    build_alpaca_mleg_order_request,
    build_profile_cli_account_check_argv,
    build_profile_cli_env_check_argv,
    deterministic_client_order_id,
    check_alpaca_paper_credentials,
    check_alpaca_profile_cli_credentials,
    effective_transport_limit,
    filter_ready_payloads,
    normalize_paper_base_url,
    profile_cli_submit_blocked,
    run_paper_payload_transport,
    submit_alpaca_paper_mleg_order,
    transport_error_raw,
    validate_paper_endpoint,
)
from qops.execution.mcp_response import normalize_mcp_response
from qops.execution.paper_payload_candidate import PaperPayloadCandidate
from qops.schemas.playbook import AllowedPlaybook


def _ready_payload(**overrides: object) -> PaperPayloadCandidate:
    base = dict(
        payload_id="pay001",
        approval_id="app001",
        symbol="SPY",
        trade_date="2026-06-13",
        structure_type=AllowedPlaybook.BULL_CALL_SPREAD.value,
        order_class="mleg",
        order_type="limit",
        time_in_force="day",
        qty=1,
        limit_price=1.05,
        max_loss=1.05,
        max_profit=3.95,
        reward_risk=3.76,
        pmp=0.35,
        pmp_source="short_leg_delta_proxy",
        pmp_confidence="LOW",
        expected_value=0.10,
        long_leg_symbol="SPY260620C00420000",
        short_leg_symbol="SPY260620C00425000",
        long_leg_side="buy",
        short_leg_side="sell",
        long_leg_qty=1,
        short_leg_qty=1,
        expiration="2026-06-20",
        approval_status="APPROVED_FOR_PAPER_REVIEW",
        payload_status="PAPER_PAYLOAD_READY",
        payload_reason="paper_payload_fields_valid",
        failure_reasons="",
        provenance="payload_c1_paper_candidate",
    )
    base.update(overrides)
    return PaperPayloadCandidate(**base)  # type: ignore[arg-type]


def test_filter_only_ready() -> None:
    rows = [_ready_payload(), _ready_payload(payload_status="REJECTED")]
    assert len(filter_ready_payloads(rows)) == 1


def test_dry_run_does_not_call_alpaca() -> None:
    with patch(
        "qops.execution.alpaca_paper_bridge.submit_alpaca_paper_mleg_order",
    ) as mocked:
        results, fatal = run_paper_payload_transport([_ready_payload()], submit_paper=False)
        mocked.assert_not_called()
    assert fatal is None
    assert len(results) == 1
    assert results[0].transport_status == "PAPER_DRY_RUN_READY"
    assert results[0].dry_run is True


def test_missing_paper_endpoint_fails_validation() -> None:
    ok, detail = validate_paper_endpoint(None)
    assert not ok
    assert detail == "missing_paper_base_url"


def test_live_endpoint_fails() -> None:
    ok, detail = validate_paper_endpoint("https://api.alpaca.markets")
    assert not ok
    assert detail == "live_endpoint_forbidden"


def test_paper_endpoint_passes() -> None:
    ok, detail = validate_paper_endpoint(CANONICAL_PAPER_BASE_URL)
    assert ok
    assert detail == "paper_endpoint_ok"
    assert normalize_paper_base_url(f"{CANONICAL_PAPER_BASE_URL}/") == CANONICAL_PAPER_BASE_URL


def test_missing_credentials_fail_submit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPACA_PAPER_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_PAPER_SECRET_KEY", raising=False)
    monkeypatch.delenv("ALPACA_PAPER_BASE_URL", raising=False)
    results, fatal = run_paper_payload_transport([_ready_payload()], submit_paper=True, limit=1)
    assert fatal is not None
    assert results == []


def test_normalized_response_exact_five_keys() -> None:
    raw = {
        "accepted": True,
        "status": "accepted",
        "broker_mode": "paper",
        "external_order_id": "oid-1",
        "message": "ok",
    }
    normalized = normalize_mcp_response(raw)
    assert normalized.broker_mode == "paper"
    assert normalized.external_order_id == "oid-1"


def test_transport_error_raw_normalizes() -> None:
    raw = transport_error_raw("boom")
    normalized = normalize_mcp_response(raw)
    assert normalized.accepted is False
    assert normalized.message == "boom"


def test_submit_mode_defaults_limit_to_one() -> None:
    assert effective_transport_limit(submit_paper=True, limit=None) == 1
    assert effective_transport_limit(submit_paper=True, limit=5) == 5


def test_submit_uses_injected_fn() -> None:
    def fake_submit(
        _creds: AlpacaPaperCredentials,
        _payload: PaperPayloadCandidate,
    ) -> dict:
        return {
            "accepted": True,
            "status": "accepted",
            "broker_mode": "paper",
            "external_order_id": "paper-99",
            "message": "accepted",
        }

    creds = AlpacaPaperCredentials(
        api_key="k",
        secret_key="s",
        base_url=CANONICAL_PAPER_BASE_URL,
        env_pair_label="test",
    )
    with patch(
        "qops.execution.alpaca_paper_bridge.resolve_alpaca_paper_credentials",
        return_value=creds,
    ):
        results, fatal = run_paper_payload_transport(
            [_ready_payload()],
            submit_paper=True,
            limit=1,
            submit_fn=fake_submit,
        )
    assert fatal is None
    assert results[0].transport_status == "PAPER_SUBMITTED"
    assert results[0].external_order_id == "paper-99"


def test_build_mleg_request_debit_positive_limit() -> None:
    req = build_alpaca_mleg_order_request(_ready_payload())
    assert req.limit_price == 1.05
    assert len(req.legs) == 2
    assert req.client_order_id == deterministic_client_order_id(_ready_payload())


def test_build_mleg_request_credit_negative_limit() -> None:
    req = build_alpaca_mleg_order_request(
        _ready_payload(
            structure_type=AllowedPlaybook.BULL_PUT_CREDIT_SPREAD.value,
            limit_price=0.85,
        )
    )
    assert req.limit_price == -0.85


def test_env_check_ready_with_paper_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPACA_PAPER_API_KEY", "key")
    monkeypatch.setenv("ALPACA_PAPER_SECRET_KEY", "secret")
    monkeypatch.setenv("ALPACA_PAPER_BASE_URL", CANONICAL_PAPER_BASE_URL)
    check = check_alpaca_paper_credentials()
    assert check.credential_status == "READY"
    assert check.endpoint_ok is True


def test_non_ready_not_in_dry_run_results() -> None:
    results, _ = run_paper_payload_transport(
        [_ready_payload(payload_status="REJECTED")],
        submit_paper=False,
    )
    assert results == []


@patch("alpaca.trading.client.TradingClient")
def test_submit_alpaca_paper_mleg_order_maps_response(mock_client_cls: MagicMock) -> None:
    from alpaca.trading.enums import OrderStatus

    order = MagicMock()
    order.id = "abc"
    order.status = OrderStatus.ACCEPTED
    mock_client_cls.return_value.submit_order.return_value = order

    creds = AlpacaPaperCredentials(
        api_key="k",
        secret_key="s",
        base_url=CANONICAL_PAPER_BASE_URL,
        env_pair_label="ALPACA_PAPER_*",
    )
    raw = submit_alpaca_paper_mleg_order(creds, _ready_payload())
    normalize_mcp_response(raw)
    mock_client_cls.assert_called_once()
    call_kwargs = mock_client_cls.call_args.kwargs
    assert call_kwargs["paper"] is True
    assert call_kwargs["url_override"] == CANONICAL_PAPER_BASE_URL


def test_auth_mode_defaults_to_env_triplet() -> None:
    with patch("examples.submit_paper_payload_candidates._print_env_triplet_check", return_value=0):
        with pytest.raises(SystemExit) as exc:
            submit_main(["--env-check"])
        assert exc.value.code == 0


def test_profile_cli_argv_includes_quiet_not_live_or_secret() -> None:
    for argv in (build_profile_cli_env_check_argv(), build_profile_cli_account_check_argv()):
        assert "--quiet" in argv
        assert "--live" not in argv
        assert "--secret" not in argv


def _fake_cli_run_both_ok(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(cmd, 0, stdout="{}", stderr="")


def test_profile_cli_ready_when_profile_and_account_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ALPACA_LIVE_TRADE", raising=False)
    with patch("qops.execution.alpaca_paper_bridge.shutil.which", return_value="/usr/bin/alpaca"):
        with patch(
            "qops.execution.alpaca_paper_bridge.submit_alpaca_paper_mleg_order",
        ) as mocked_submit:
            check = check_alpaca_profile_cli_credentials(run=_fake_cli_run_both_ok)
            mocked_submit.assert_not_called()
    assert check.credential_status == "READY_PROFILE_AUTH_PAPER_DEFAULT"
    assert check.live_env_status == "missing"


def test_profile_cli_live_env_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPACA_LIVE_TRADE", "true")
    with patch("qops.execution.alpaca_paper_bridge.shutil.which", return_value="/usr/bin/alpaca"):
        with patch("qops.execution.alpaca_paper_bridge.subprocess.run") as mocked_run:
            check = check_alpaca_profile_cli_credentials()
            mocked_run.assert_not_called()
    assert check.credential_status == "LIVE_ENV_FORBIDDEN"
    assert check.live_env_status == "true"


def test_profile_cli_account_check_failed() -> None:
    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if "account" in cmd:
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="err")
        return subprocess.CompletedProcess(cmd, 0, stdout="{}", stderr="")

    with patch("qops.execution.alpaca_paper_bridge.shutil.which", return_value="/usr/bin/alpaca"):
        check = check_alpaca_profile_cli_credentials(run=fake_run)
    assert check.credential_status == "ACCOUNT_CHECK_FAILED"


def test_profile_cli_cli_not_found() -> None:
    with patch("qops.execution.alpaca_paper_bridge.shutil.which", return_value=None):
        check = check_alpaca_profile_cli_credentials()
    assert check.credential_status == "CLI_NOT_FOUND"


def test_profile_cli_exit_code_2_auth_failed() -> None:
    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 2, stdout="", stderr="auth")

    with patch("qops.execution.alpaca_paper_bridge.shutil.which", return_value="/usr/bin/alpaca"):
        check = check_alpaca_profile_cli_credentials(run=fake_run)
    assert check.credential_status == "AUTH_FAILED"
    assert check.detail == "alpaca_cli_profile_exit_code_2"


def test_profile_cli_submit_blocked() -> None:
    assert profile_cli_submit_blocked("profile_cli", submit_paper=True) == PROFILE_CLI_SUBMIT_NOT_IMPLEMENTED
    assert profile_cli_submit_blocked("env_triplet", submit_paper=True) is None


def test_submit_paper_profile_cli_fails_closed() -> None:
    with pytest.raises(SystemExit) as exc:
        submit_main(["--submit-paper", "--auth-mode", "profile_cli"])
    assert exc.value.code == 1


def test_env_triplet_submit_path_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPACA_PAPER_API_KEY", "key")
    monkeypatch.setenv("ALPACA_PAPER_SECRET_KEY", "secret")
    monkeypatch.setenv("ALPACA_PAPER_BASE_URL", CANONICAL_PAPER_BASE_URL)

    def fake_submit(_creds: AlpacaPaperCredentials, _payload: PaperPayloadCandidate) -> dict:
        return {
            "accepted": True,
            "status": "accepted",
            "broker_mode": "paper",
            "external_order_id": "oid",
            "message": "ok",
        }

    results, fatal = run_paper_payload_transport(
        [_ready_payload()],
        submit_paper=True,
        limit=1,
        submit_fn=fake_submit,
    )
    assert fatal is None
    assert results[0].transport_status == "PAPER_SUBMITTED"
