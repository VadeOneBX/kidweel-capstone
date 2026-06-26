"""Human-in-the-loop boundary before Alpaca paper order submission."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from qops.execution.paper_payload_candidate import PaperPayloadCandidate
from qops.guardrails.base import evaluate_guardrails
from qops.guardrails.tool_payload import guardrail_candidate_from_paper_payload
from qops.schemas.hitl import (
    DEFAULT_ACTION_WITHOUT_APPROVAL,
    HITL_PACKET,
    STATUS_APPROVAL_REQUIRED,
    STATUS_APPROVED_BY_OPERATOR,
    STATUS_CLEAN_REJECT,
    STATUS_LIVE_ENV_FORBIDDEN,
    STATUS_REJECTED_BY_OPERATOR,
    STATUS_WATCH_PENDING_REVIEW,
    HitlApprovalItem,
)

_PENDING_DIRNAME = "pending"


def env_is_live() -> bool:
    raw = os.environ.get("ALPACA_LIVE_TRADE")
    if raw is None:
        return False
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def hitl_root(base_dir: Path | None = None) -> Path:
    root = (base_dir or Path.cwd()).resolve()
    return root / "logs" / "hitl"


def pending_approval_path(candidate_id: str, base_dir: Path | None = None) -> Path:
    return hitl_root(base_dir) / _PENDING_DIRNAME / f"{candidate_id}.json"


def audit_artifact_path(candidate_id: str, base_dir: Path | None = None) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    return hitl_root(base_dir) / f"{stamp}_{candidate_id}_hitl_approval.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_audit_record(item: HitlApprovalItem) -> dict[str, Any]:
    return {
        "packet": HITL_PACKET,
        "candidate_id": item.candidate_id,
        "symbol": item.symbol,
        "structure": item.structure,
        "approval_status": item.approval_status,
        "paper_submit_allowed": item.paper_submit_allowed(),
        "operator_decision": item.operator_decision,
        "operator_reason": item.operator_reason,
        "paper_only": True,
        "live_env_forbidden": True,
        "trace_id": item.trace_id,
        "source_artifacts": list(item.source_artifacts),
        "default_action_without_approval": DEFAULT_ACTION_WITHOUT_APPROVAL,
    }


def write_audit_artifact(item: HitlApprovalItem, base_dir: Path | None = None) -> Path:
    path = audit_artifact_path(item.candidate_id, base_dir=base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_audit_record(item)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def save_pending_approval(item: HitlApprovalItem, base_dir: Path | None = None) -> Path:
    path = pending_approval_path(item.candidate_id, base_dir=base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(item.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_pending_approval(candidate_id: str, base_dir: Path | None = None) -> HitlApprovalItem | None:
    path = pending_approval_path(candidate_id, base_dir=base_dir)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return HitlApprovalItem.from_dict(data)


def list_pending_approvals(base_dir: Path | None = None) -> list[HitlApprovalItem]:
    pending_dir = hitl_root(base_dir) / _PENDING_DIRNAME
    if not pending_dir.is_dir():
        return []
    items: list[HitlApprovalItem] = []
    for path in sorted(pending_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        item = HitlApprovalItem.from_dict(data)
        if item.approval_status == STATUS_APPROVAL_REQUIRED:
            items.append(item)
    return items


def _legs_from_payload(payload: PaperPayloadCandidate) -> list[dict[str, Any]]:
    legs: list[dict[str, Any]] = []
    if payload.long_leg_symbol:
        legs.append(
            {
                "symbol": payload.long_leg_symbol,
                "side": payload.long_leg_side,
                "qty": payload.long_leg_qty,
            }
        )
    if payload.short_leg_symbol:
        legs.append(
            {
                "symbol": payload.short_leg_symbol,
                "side": payload.short_leg_side,
                "qty": payload.short_leg_qty,
            }
        )
    return legs


def build_approval_item_from_payload(
    payload: PaperPayloadCandidate,
    *,
    gate_status: str = "gates_passed",
    trace_id: str | None = None,
    source_artifacts: list[str] | None = None,
) -> HitlApprovalItem:
    max_loss = float(payload.max_loss) if payload.max_loss is not None else 0.0
    return HitlApprovalItem(
        candidate_id=payload.payload_id,
        symbol=payload.symbol,
        playbook=payload.structure_type,
        structure=payload.structure_type,
        legs=_legs_from_payload(payload),
        max_profit=payload.max_profit,
        max_loss=max_loss,
        rr_actual=payload.reward_risk,
        pmp=payload.pmp,
        ev=payload.expected_value,
        gate_status=gate_status,
        approval_status=STATUS_APPROVAL_REQUIRED,
        operator_decision=None,
        operator_reason=None,
        paper_only=True,
        live_env_forbidden=True,
        created_at=_utc_now_iso(),
        approved_at=None,
        rejected_at=None,
        trace_id=trace_id,
        source_artifacts=list(source_artifacts or []),
    )


def load_or_create_approval(
    payload: PaperPayloadCandidate,
    *,
    base_dir: Path | None = None,
    trace_id: str | None = None,
    source_artifacts: list[str] | None = None,
) -> HitlApprovalItem:
    existing = load_pending_approval(payload.payload_id, base_dir=base_dir)
    if existing is not None:
        return existing
    item = build_approval_item_from_payload(
        payload,
        trace_id=trace_id,
        source_artifacts=source_artifacts,
    )
    save_pending_approval(item, base_dir=base_dir)
    write_audit_artifact(item, base_dir=base_dir)
    return item


def apply_operator_decision(
    candidate_id: str,
    decision: str,
    reason: str,
    *,
    base_dir: Path | None = None,
) -> HitlApprovalItem:
    item = load_pending_approval(candidate_id, base_dir=base_dir)
    if item is None:
        raise FileNotFoundError(f"hitl_pending_not_found:{candidate_id}")

    now = _utc_now_iso()
    normalized = decision.strip().lower()
    if normalized == "approve":
        item.approval_status = STATUS_APPROVED_BY_OPERATOR
        item.operator_decision = "approve"
        item.approved_at = now
        item.rejected_at = None
    elif normalized == "reject":
        item.approval_status = STATUS_REJECTED_BY_OPERATOR
        item.operator_decision = "reject"
        item.rejected_at = now
        item.approved_at = None
    else:
        raise ValueError(f"invalid_operator_decision:{decision}")

    item.operator_reason = reason.strip() or None
    save_pending_approval(item, base_dir=base_dir)
    write_audit_artifact(item, base_dir=base_dir)
    return item


@dataclass(frozen=True, slots=True)
class HitlTransportGateResult:
    status: str
    paper_submit_allowed: bool
    detail: str
    approval: HitlApprovalItem | None = None


def _is_watch_candidate(payload: PaperPayloadCandidate) -> bool:
    status = (payload.approval_status or "").upper()
    return "WATCH" in status


def evaluate_paper_transport_hitl(
    payload: PaperPayloadCandidate,
    *,
    candidate_passed_existing_gates: bool,
    base_dir: Path | None = None,
) -> HitlTransportGateResult:
    if env_is_live():
        return HitlTransportGateResult(
            status=STATUS_LIVE_ENV_FORBIDDEN,
            paper_submit_allowed=False,
            detail="ALPACA_LIVE_TRADE_true",
        )

    if not candidate_passed_existing_gates:
        return HitlTransportGateResult(
            status=STATUS_CLEAN_REJECT,
            paper_submit_allowed=False,
            detail="candidate_failed_existing_gates",
        )

    approval = load_or_create_approval(payload, base_dir=base_dir)

    if approval.approval_status == STATUS_APPROVED_BY_OPERATOR:
        return HitlTransportGateResult(
            status=STATUS_APPROVED_BY_OPERATOR,
            paper_submit_allowed=True,
            detail="operator_approved",
            approval=approval,
        )

    if approval.approval_status == STATUS_REJECTED_BY_OPERATOR:
        return HitlTransportGateResult(
            status=STATUS_REJECTED_BY_OPERATOR,
            paper_submit_allowed=False,
            detail="operator_rejected",
            approval=approval,
        )

    if _is_watch_candidate(payload):
        return HitlTransportGateResult(
            status=STATUS_WATCH_PENDING_REVIEW,
            paper_submit_allowed=False,
            detail="watch_pending_operator_decision",
            approval=approval,
        )

    return HitlTransportGateResult(
        status=STATUS_APPROVAL_REQUIRED,
        paper_submit_allowed=False,
        detail=DEFAULT_ACTION_WITHOUT_APPROVAL,
        approval=approval,
    )


def paper_submit_allowed_for_candidate(
    candidate_id: str,
    *,
    base_dir: Path | None = None,
) -> bool:
    if env_is_live():
        return False
    item = load_pending_approval(candidate_id, base_dir=base_dir)
    if item is None:
        return False
    return item.paper_submit_allowed()


def assert_hitl_paper_submit_allowed(
    payload: PaperPayloadCandidate,
    *,
    base_dir: Path | None = None,
) -> str | None:
    """Return error detail when submit must not proceed; None when allowed."""
    guardrail_result = evaluate_guardrails(
        guardrail_candidate_from_paper_payload(payload),
        base_dir=base_dir,
        write_audit=False,
    )
    if not guardrail_result.ok:
        return f"guardrail_blocked:{guardrail_result.reason_code or guardrail_result.status}:{guardrail_result.message}"

    gate = evaluate_paper_transport_hitl(
        payload,
        candidate_passed_existing_gates=payload.payload_status == "PAPER_PAYLOAD_READY",
        base_dir=base_dir,
    )
    if gate.paper_submit_allowed:
        return None
    return f"hitl_blocked:{gate.status}:{gate.detail}"


def try_openai_agents_hitl_interrupt() -> bool:
    """True when OpenAI Agents SDK HITL is available (optional; repo-local path is canonical)."""
    try:
        import agents  # type: ignore[import-not-found]  # noqa: F401
    except ImportError:
        return False
    return True
