"""RR sufficiency audit against PMP-implied requirements."""

from __future__ import annotations

import math

from qops.risk.pmp_policy import required_rr_from_pmp, validate_pmp

# Schemas are canonical handoff contracts.
# Do not rename, repurpose, or silently widen schema fields once imported downstream.
# Schema changes must be explicit, additive where possible, and updated across all
# dependents in the same packet.

from qops.schemas.structure import TradeStructureCandidate


def rr_is_sufficient(rr_actual: float, rr_required: float) -> tuple[bool, str]:
    """Return (pass_flag, reason) for whether actual RR clears required RR."""
    if not math.isfinite(rr_actual) or rr_actual <= 0.0:
        return False, "invalid_rr_actual"
    if not math.isfinite(rr_required) or rr_required <= 0.0:
        return False, "invalid_rr_required"
    if rr_actual >= rr_required:
        return True, "pass"
    return False, "insufficient_rr"


def audit_structure_rr(
    structure: TradeStructureCandidate,
    pmp: float,
) -> tuple[bool, float, float, str]:
    """
    Return (pass_flag, rr_required, rr_actual, reason).

    Uses structure.rr_actual and PMP-derived required RR.
    """
    rr_actual = structure.rr_actual
    if not math.isfinite(rr_actual) or rr_actual <= 0.0:
        return False, 0.0, rr_actual, "invalid_rr"

    try:
        validate_pmp(pmp)
        rr_required = required_rr_from_pmp(pmp)
    except ValueError:
        return False, 0.0, rr_actual, "invalid_pmp"

    pass_flag, reason = rr_is_sufficient(rr_actual=rr_actual, rr_required=rr_required)
    return pass_flag, rr_required, rr_actual, reason
