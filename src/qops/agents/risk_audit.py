"""Risk audit specialist before guardrail stack (no promotion authority)."""

from __future__ import annotations

from dataclasses import dataclass

from qops.schemas.candidate_memo import (
    MEMO_CLEAN_REJECT,
    MEMO_PASS,
    MEMO_WATCH,
    CandidateMemo,
)
from qops.schemas.playbook import AllowedPlaybook

AGENT_NAME = "risk_audit"

_ALLOWED_STRUCTURES = frozenset(
    {
        AllowedPlaybook.BULL_CALL_SPREAD.value,
        AllowedPlaybook.BEAR_PUT_SPREAD.value,
        AllowedPlaybook.BULL_PUT_CREDIT_SPREAD.value,
        AllowedPlaybook.BEAR_CALL_CREDIT_SPREAD.value,
    }
)


@dataclass(frozen=True, slots=True)
class RiskAuditResult:
    ok: bool
    gate_status: str
    reason_code: str | None
    message: str
    memo: CandidateMemo


def audit_candidate_memo(memo: CandidateMemo) -> RiskAuditResult:
    """Verify policy conformance; cannot promote WATCH or approve transport."""
    if memo.gate_status == MEMO_WATCH:
        return RiskAuditResult(
            ok=True,
            gate_status=MEMO_WATCH,
            reason_code=memo.reason_code,
            message="watch_preserved_for_operator_review",
            memo=memo,
        )

    if memo.gate_status == MEMO_CLEAN_REJECT:
        return RiskAuditResult(
            ok=False,
            gate_status=MEMO_CLEAN_REJECT,
            reason_code=memo.reason_code or "clean_reject",
            message="clean_reject_preserved",
            memo=memo,
        )

    structure = (memo.selected_structure or "").strip().upper()
    if structure and structure not in _ALLOWED_STRUCTURES:
        audited = memo.model_copy(
            update={
                "gate_status": MEMO_CLEAN_REJECT,
                "reason_code": "structure_not_allowed",
                "notes": [*memo.notes, "risk_audit:structure_not_allowed"],
            }
        )
        return RiskAuditResult(
            ok=False,
            gate_status=MEMO_CLEAN_REJECT,
            reason_code="structure_not_allowed",
            message="structure_not_in_policy",
            memo=audited,
        )

    if memo.gate_status == MEMO_PASS:
        if memo.max_loss is None or memo.max_loss <= 0:
            audited = memo.model_copy(
                update={
                    "gate_status": MEMO_CLEAN_REJECT,
                    "reason_code": "invalid_max_loss",
                }
            )
            return RiskAuditResult(
                ok=False,
                gate_status=MEMO_CLEAN_REJECT,
                reason_code="invalid_max_loss",
                message="pass_requires_positive_max_loss",
                memo=audited,
            )

    return RiskAuditResult(
        ok=memo.gate_status == MEMO_PASS,
        gate_status=memo.gate_status,
        reason_code=memo.reason_code,
        message="risk_audit_complete",
        memo=memo,
    )


def promote_watch_to_pass(_memo: CandidateMemo) -> CandidateMemo:
    """Forbidden: risk audit cannot promote WATCH to PASS."""
    raise PermissionError("risk_audit_cannot_promote_watch_to_pass")
