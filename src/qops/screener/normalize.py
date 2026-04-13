"""Validate and normalize screened-candidate handoff objects."""

from __future__ import annotations

import math

# Schemas are canonical handoff contracts.
# Do not rename, repurpose, or silently widen schema fields once imported downstream.
# Schema changes must be explicit, additive where possible, and updated across all
# dependents in the same packet.

from qops.schemas.candidate import ScreenedCandidate
from qops.schemas.playbook import AllowedPlaybook, StructureBias

_EXECUTABLE_PLAYBOOKS: frozenset[AllowedPlaybook] = frozenset(
    {
        AllowedPlaybook.BULL_CALL_SPREAD,
        AllowedPlaybook.BEAR_PUT_SPREAD,
    }
)


def normalize_candidate(candidate: ScreenedCandidate) -> ScreenedCandidate:
    """
    Validate and return a canonical screened candidate.

    This function validates only; it does not re-derive canonical upstream fields.
    """
    if not isinstance(candidate, ScreenedCandidate):
        raise TypeError("candidate must be ScreenedCandidate")
    if not candidate.symbol or not candidate.symbol.strip():
        raise ValueError("candidate.symbol must be non-empty")
    if not math.isfinite(candidate.underlying_price) or candidate.underlying_price <= 0.0:
        raise ValueError("candidate.underlying_price must be > 0")
    if candidate.dte_target < 0:
        raise ValueError("candidate.dte_target must be >= 0")
    if not candidate.expiry_target or not candidate.expiry_target.strip():
        raise ValueError("candidate.expiry_target must be non-empty")
    if candidate.confidence is None:
        raise ValueError("candidate.confidence is required and canonical")
    if not (0 <= candidate.confidence <= 100):
        raise ValueError("candidate.confidence must be between 0 and 100")

    if candidate.regime_label is None:
        raise ValueError("candidate.regime_label is required and canonical")
    if candidate.structure_bias is None:
        raise ValueError("candidate.structure_bias is required and canonical")
    if candidate.allowed_playbook is None:
        raise ValueError("candidate.allowed_playbook is required")

    if candidate.allowed_playbook in _EXECUTABLE_PLAYBOOKS:
        if not candidate.tradeability_pass:
            raise ValueError("executable candidate requires tradeability_pass=True")
        if not candidate.liquidity_pass:
            raise ValueError("executable candidate requires liquidity_pass=True")

    if (
        candidate.allowed_playbook == AllowedPlaybook.BULL_CALL_SPREAD
        and candidate.structure_bias != StructureBias.BULL_CALL_SPREAD
    ):
        raise ValueError(
            "allowed_playbook BULL_CALL_SPREAD must align with structure_bias BULL_CALL_SPREAD"
        )
    if (
        candidate.allowed_playbook == AllowedPlaybook.BEAR_PUT_SPREAD
        and candidate.structure_bias != StructureBias.BEAR_PUT_SPREAD
    ):
        raise ValueError(
            "allowed_playbook BEAR_PUT_SPREAD must align with structure_bias BEAR_PUT_SPREAD"
        )

    return candidate
