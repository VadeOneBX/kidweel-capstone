"""OPENAI-AGENTS-HITL-PAPER-TRANSPORT-C1 tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from qops.execution.alpaca_paper_bridge import (
    CANONICAL_PAPER_BASE_URL,
    AlpacaPaperCredentials,
    run_paper_payload_transport,
    submit_alpaca_paper_mleg_order,
)
from qops.execution.hitl_paper_transport import (
    evaluate_paper_transport_hitl,
    hitl_root,
    load_or_create_approval,
)
from qops.execution.paper_payload_candidate import PaperPayloadCandidate
from qops.schemas.hitl import (
    STATUS_APPROVAL_REQUIRED,
    STATUS_APPROVED_BY_OPERATOR,
    STATUS_LIVE_ENV_FORBIDDEN,
    STATUS_REJECTED_BY_OPERATOR,
    STATUS_WATCH_PENDING_REVIEW,
)
from qops.schemas.playbook import AllowedPlaybook

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _ready_payload(**overrides: object) -> PaperPayloadCandidate:
    base = dict(
        payload_id="pay-hitl-001",
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


def _approve_via_cli(candidate_id: str, base_dir: Path, reason: str = "operator approved paper test") -> None:
    subprocess.run(
        [
            sys.executable,
            str(_REPO_ROOT / "scripts/hitl_review.py"),
            "--base-dir",
            str(base_dir),
            "--candidate-id",
            candidate_id,
            "--decision",
            "approve",
            "--reason",
            reason,
        ],
        check=True,
        cwd=_REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(_REPO_ROOT / "src")},
    )


def _reject_via_cli(candidate_id: str, base_dir: Path, reason: str = "RR/PMP not acceptable") -> None:
    subprocess.run(
        [
            sys.executable,
            str(_REPO_ROOT / "scripts/hitl_review.py"),
            "--base-dir",
            str(base_dir),
            "--candidate-id",
            candidate_id,
            "--decision",
            "reject",
            "--reason",
            reason,
        ],
        check=True,
        cwd=_REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(_REPO_ROOT / "src")},
    )


def test_live_env_returns_live_env_forbidden(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ALPACA_LIVE_TRADE", "true")
    payload = _ready_payload()
    gate = evaluate_paper_transport_hitl(
        payload,
        candidate_passed_existing_gates=True,
        base_dir=tmp_path,
    )
    assert gate.status == STATUS_LIVE_ENV_FORBIDDEN
    assert gate.paper_submit_allowed is False

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
            [payload],
            submit_paper=True,
            base_dir=tmp_path,
        )
    assert fatal == "LIVE_ENV_FORBIDDEN"
    assert results == []


def test_candidate_without_approval_cannot_submit(tmp_path: Path) -> None:
    payload = _ready_payload()
    load_or_create_approval(payload, base_dir=tmp_path)
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
            [payload],
            submit_paper=True,
            base_dir=tmp_path,
        )
    assert fatal is None
    assert len(results) == 1
    assert results[0].transport_status == "PAPER_SKIPPED"
    assert results[0].failure_reasons == STATUS_APPROVAL_REQUIRED


def test_rejected_candidate_cannot_submit(tmp_path: Path) -> None:
    payload = _ready_payload()
    load_or_create_approval(payload, base_dir=tmp_path)
    _reject_via_cli(payload.payload_id, tmp_path)

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
            [payload],
            submit_paper=True,
            base_dir=tmp_path,
        )
    assert fatal is None
    assert results[0].transport_status == "PAPER_SKIPPED"
    assert results[0].failure_reasons == STATUS_REJECTED_BY_OPERATOR


def test_approved_candidate_can_proceed_to_paper_transport(tmp_path: Path) -> None:
    payload = _ready_payload()
    load_or_create_approval(payload, base_dir=tmp_path)
    _approve_via_cli(payload.payload_id, tmp_path)

    def fake_submit(
        _creds: AlpacaPaperCredentials,
        _payload: PaperPayloadCandidate,
    ) -> dict:
        return {
            "accepted": True,
            "status": "accepted",
            "broker_mode": "paper",
            "external_order_id": "paper-hitl-1",
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
            [payload],
            submit_paper=True,
            base_dir=tmp_path,
            submit_fn=fake_submit,
        )
    assert fatal is None
    assert results[0].transport_status == "PAPER_SUBMITTED"


def test_watch_candidate_remains_unresolved_without_operator_decision(tmp_path: Path) -> None:
    payload = _ready_payload(approval_status="WATCH_PENDING_OPERATOR")
    gate = evaluate_paper_transport_hitl(
        payload,
        candidate_passed_existing_gates=True,
        base_dir=tmp_path,
    )
    assert gate.status == STATUS_WATCH_PENDING_REVIEW
    assert gate.paper_submit_allowed is False


def test_audit_artifact_written_for_approval_request(tmp_path: Path) -> None:
    payload = _ready_payload()
    load_or_create_approval(payload, base_dir=tmp_path)
    audits = list((hitl_root(tmp_path)).glob("*_hitl_approval.json"))
    assert len(audits) == 1
    record = json.loads(audits[0].read_text(encoding="utf-8"))
    assert record["packet"] == "OPENAI-AGENTS-HITL-PAPER-TRANSPORT-C1"
    assert record["approval_status"] == STATUS_APPROVAL_REQUIRED
    assert record["paper_submit_allowed"] is False


def test_audit_artifact_updated_for_operator_decision(tmp_path: Path) -> None:
    payload = _ready_payload()
    load_or_create_approval(payload, base_dir=tmp_path)
    _approve_via_cli(payload.payload_id, tmp_path)
    audits = sorted((hitl_root(tmp_path)).glob("*_hitl_approval.json"))
    assert len(audits) >= 2
    final = json.loads(audits[-1].read_text(encoding="utf-8"))
    assert final["approval_status"] == STATUS_APPROVED_BY_OPERATOR
    assert final["paper_submit_allowed"] is True
    assert final["operator_decision"] == "approve"


def test_hitl_review_cli_list_and_lifecycle(tmp_path: Path) -> None:
    payload = _ready_payload(payload_id="pay-cli-001")
    load_or_create_approval(payload, base_dir=tmp_path)

    list_proc = subprocess.run(
        [
            sys.executable,
            str(_REPO_ROOT / "scripts/hitl_review.py"),
            "--base-dir",
            str(tmp_path),
            "--list-pending",
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=_REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(_REPO_ROOT / "src")},
    )
    assert STATUS_APPROVAL_REQUIRED in list_proc.stdout
    assert "pay-cli-001" in list_proc.stdout

    reject_proc = subprocess.run(
        [
            sys.executable,
            str(_REPO_ROOT / "scripts/hitl_review.py"),
            "--base-dir",
            str(tmp_path),
            "--candidate-id",
            "pay-cli-001",
            "--decision",
            "reject",
            "--reason",
            "RR/PMP not acceptable",
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=_REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(_REPO_ROOT / "src")},
    )
    reject_payload = json.loads(reject_proc.stdout)
    assert reject_payload["status"] == STATUS_REJECTED_BY_OPERATOR
    assert reject_payload["paper_submit_allowed"] is False

    payload2 = _ready_payload(payload_id="pay-cli-002")
    load_or_create_approval(payload2, base_dir=tmp_path)
    approve_proc = subprocess.run(
        [
            sys.executable,
            str(_REPO_ROOT / "scripts/hitl_review.py"),
            "--base-dir",
            str(tmp_path),
            "--candidate-id",
            "pay-cli-002",
            "--decision",
            "approve",
            "--reason",
            "operator approved paper test",
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=_REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(_REPO_ROOT / "src")},
    )
    approve_payload = json.loads(approve_proc.stdout)
    assert approve_payload["status"] == STATUS_APPROVED_BY_OPERATOR
    assert approve_payload["paper_submit_allowed"] is True


def test_submit_alpaca_paper_mleg_order_blocked_without_approval(tmp_path: Path) -> None:
    payload = _ready_payload()
    load_or_create_approval(payload, base_dir=tmp_path)
    creds = AlpacaPaperCredentials(
        api_key="k",
        secret_key="s",
        base_url=CANONICAL_PAPER_BASE_URL,
        env_pair_label="test",
    )
    with patch("alpaca.trading.client.TradingClient"):
        raw = submit_alpaca_paper_mleg_order(creds, payload, base_dir=tmp_path)
    assert raw["accepted"] is False
    assert "hitl_blocked" in raw["message"]
