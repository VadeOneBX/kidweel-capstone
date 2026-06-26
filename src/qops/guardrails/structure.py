"""Defined-risk structure guardrails."""

from __future__ import annotations

from qops.guardrails.base import (
    STATUS_STRUCTURE_NOT_ALLOWED,
    STATUS_UNDEFINED_RISK_REJECTED,
    GuardrailCandidate,
    GuardrailResult,
)
from qops.schemas.playbook import AllowedPlaybook

_UNDEFINED_RISK_STRUCTURES = frozenset(
    {
        "UNDEFINED_RISK",
        "SHORT_STRANGLE",
        "SHORT_STRADDLE",
        "NAKED_CALL",
        "NAKED_PUT",
    }
)

_POLICY_DEFINED_RISK_EXECUTABLE = frozenset(
    {
        AllowedPlaybook.BULL_CALL_SPREAD.value,
        AllowedPlaybook.BEAR_PUT_SPREAD.value,
        AllowedPlaybook.BULL_PUT_CREDIT_SPREAD.value,
        AllowedPlaybook.BEAR_CALL_CREDIT_SPREAD.value,
    }
)


def allowed_defined_risk_structures() -> frozenset[str]:
    return _POLICY_DEFINED_RISK_EXECUTABLE


def check_structure_allowed(candidate: GuardrailCandidate) -> GuardrailResult:
    structure = (candidate.structure or "").strip().upper()
    if not structure:
        return GuardrailResult.reject(
            status=STATUS_STRUCTURE_NOT_ALLOWED,
            reason_code=STATUS_STRUCTURE_NOT_ALLOWED,
            message="missing_structure",
            details={"structure": candidate.structure},
        )
    if structure in _UNDEFINED_RISK_STRUCTURES:
        return GuardrailResult.reject(
            status=STATUS_UNDEFINED_RISK_REJECTED,
            reason_code=STATUS_UNDEFINED_RISK_REJECTED,
            message="undefined_risk_structure",
            details={"structure": structure},
        )
    if structure in {"UNKNOWN", "SKIP"}:
        return GuardrailResult.reject(
            status=STATUS_STRUCTURE_NOT_ALLOWED,
            reason_code=STATUS_STRUCTURE_NOT_ALLOWED,
            message="structure_not_allowed",
            details={"structure": structure},
        )
    if structure not in _POLICY_DEFINED_RISK_EXECUTABLE:
        return GuardrailResult.reject(
            status=STATUS_STRUCTURE_NOT_ALLOWED,
            reason_code=STATUS_STRUCTURE_NOT_ALLOWED,
            message="structure_not_in_repo_policy",
            details={
                "structure": structure,
                "allowed": sorted(_POLICY_DEFINED_RISK_EXECUTABLE),
            },
        )
    return GuardrailResult.pass_(message="structure_allowed")
