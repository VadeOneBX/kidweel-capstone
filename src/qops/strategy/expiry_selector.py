"""Strict expiry selection from candidate target values only."""

from __future__ import annotations

# Schemas are canonical handoff contracts.
# Do not rename, repurpose, or silently widen schema fields once imported downstream.
# Schema changes must be explicit, additive where possible, and updated across all
# dependents in the same packet.

from qops.schemas.candidate import ScreenedCandidate
from qops.strategy.constants import MIN_DTE


def select_expiry(candidate: ScreenedCandidate) -> str:
    """
    Return the candidate's target expiry if it satisfies packet constraints.

    Uses candidate.expiry_target only; does not search alternatives or infer missing values.
    """
    expiry = candidate.expiry_target.strip()
    if not expiry:
        raise ValueError("candidate.expiry_target must be non-empty")
    if candidate.dte_target < MIN_DTE:
        raise ValueError(f"candidate.dte_target must be >= {MIN_DTE}")
    return expiry
