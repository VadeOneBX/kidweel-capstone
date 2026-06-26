"""Guardrail result contract and stack orchestration."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GUARDRAIL_PACKET = "OPENAI-AGENTS-GUARDRAIL-STACK-C1"

STATUS_PASS = "PASS"
STATUS_CLEAN_REJECT = "CLEAN_REJECT"
STATUS_WATCH_PENDING_REVIEW = "WATCH_PENDING_REVIEW"
STATUS_LIVE_ENV_FORBIDDEN = "LIVE_ENV_FORBIDDEN"
STATUS_MALFORMED_PAYLOAD = "MALFORMED_PAYLOAD"
STATUS_UNDEFINED_RISK_REJECTED = "UNDEFINED_RISK_REJECTED"
STATUS_NEGATIVE_OR_ZERO_MAX_PROFIT = "NEGATIVE_OR_ZERO_MAX_PROFIT"
STATUS_INVALID_MAX_LOSS = "INVALID_MAX_LOSS"
STATUS_RR_PMP_REJECTED = "RR_PMP_REJECTED"
STATUS_EV_REJECTED = "EV_REJECTED"
STATUS_STRUCTURE_NOT_ALLOWED = "STRUCTURE_NOT_ALLOWED"
STATUS_MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"

GuardrailFn = Callable[["GuardrailCandidate"], "GuardrailResult"]


@dataclass(frozen=True, slots=True)
class GuardrailResult:
    ok: bool
    status: str
    reason_code: str | None
    message: str
    blocking: bool = True
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def pass_(cls, *, message: str = "guardrails_pass") -> GuardrailResult:
        return cls(
            ok=True,
            status=STATUS_PASS,
            reason_code=None,
            message=message,
            blocking=False,
            details={},
        )

    @classmethod
    def reject(
        cls,
        *,
        status: str,
        reason_code: str,
        message: str,
        details: dict[str, Any] | None = None,
        blocking: bool = True,
    ) -> GuardrailResult:
        return cls(
            ok=False,
            status=status,
            reason_code=reason_code,
            message=message,
            blocking=blocking,
            details=dict(details or {}),
        )


@dataclass(frozen=True, slots=True)
class GuardrailCandidate:
    """Normalized candidate for guardrail evaluation (transport / tool payload)."""

    candidate_id: str
    symbol: str
    structure: str
    legs: list[dict[str, Any]]
    max_loss: float | None
    max_profit: float | None = None
    rr_actual: float | None = None
    pmp: float | None = None
    ev: float | None = None
    paper_only: bool = True
    account_mode_paper: bool = True
    live_env_hint: bool = False
    watch_promotion_viable: bool = False


def guardrails_log_root(base_dir: Path | None = None) -> Path:
    return (base_dir or Path.cwd()).resolve() / "logs" / "guardrails"


def guardrail_audit_path(candidate_id: str, reason_code: str, base_dir: Path | None = None) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    safe_reason = (reason_code or "UNKNOWN").replace("/", "_")
    return guardrails_log_root(base_dir) / f"{stamp}_{candidate_id}_{safe_reason}.json"


def write_guardrail_audit(
    candidate: GuardrailCandidate,
    result: GuardrailResult,
    *,
    base_dir: Path | None = None,
) -> Path:
    path = guardrail_audit_path(
        candidate.candidate_id,
        result.reason_code or result.status,
        base_dir=base_dir,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "packet": GUARDRAIL_PACKET,
        "candidate_id": candidate.candidate_id,
        "symbol": candidate.symbol,
        "status": result.status,
        "reason_code": result.reason_code,
        "blocking": result.blocking,
        "paper_submit_allowed": False,
        "details": dict(result.details),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def run_guardrail_stack(
    candidate: GuardrailCandidate,
    guardrails: Sequence[GuardrailFn],
    *,
    base_dir: Path | None = None,
    write_audit: bool = True,
) -> GuardrailResult:
    for guardrail in guardrails:
        result = guardrail(candidate)
        if result.blocking and not result.ok:
            if write_audit:
                write_guardrail_audit(candidate, result, base_dir=base_dir)
            return result
    final = GuardrailResult.pass_()
    return final


def default_guardrail_stack() -> tuple[GuardrailFn, ...]:
    from qops.guardrails.economics import check_economics, check_watch_boundary
    from qops.guardrails.paper_env import check_paper_environment
    from qops.guardrails.structure import check_structure_allowed
    from qops.guardrails.tool_payload import check_leg_payload, check_required_fields

    return (
        check_paper_environment,
        check_required_fields,
        check_structure_allowed,
        check_leg_payload,
        check_economics,
        check_watch_boundary,
    )


def evaluate_guardrails(
    candidate: GuardrailCandidate,
    *,
    base_dir: Path | None = None,
    write_audit: bool = True,
) -> GuardrailResult:
    return run_guardrail_stack(
        candidate,
        default_guardrail_stack(),
        base_dir=base_dir,
        write_audit=write_audit,
    )


def transport_blocked_by_guardrails(result: GuardrailResult) -> bool:
    if result.ok:
        return False
    if result.status == STATUS_WATCH_PENDING_REVIEW:
        return True
    return result.blocking and not result.ok


def guardrails_allow_hitl(result: GuardrailResult) -> bool:
    """HITL may run only after blocking guardrails pass or WATCH boundary."""
    if result.ok and result.status == STATUS_PASS:
        return True
    if result.status == STATUS_WATCH_PENDING_REVIEW:
        return True
    return False
