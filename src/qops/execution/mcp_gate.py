"""Integration-specific gate before any MCP transport scaffolding (fail-closed)."""

from __future__ import annotations

import math

from qops.execution.mcp_models import MCPExecutionRequest


def mcp_paper_gate(request: MCPExecutionRequest) -> tuple[bool, str]:
    """
    Return (allowed, reason) for whether a request may proceed to MCP transport scaffolding.

    Denies ambiguous or invalid inputs with an explicit machine-oriented reason string.
    """
    if not isinstance(request, MCPExecutionRequest):
        return False, "invalid_request_type"

    if not request.paper_only:
        return False, "paper_only_required"

    if not math.isfinite(request.pmp) or not (0.0 < request.pmp < 1.0):
        return False, "invalid_pmp_range"

    if not math.isfinite(request.rr_actual) or request.rr_actual <= 0.0:
        return False, "invalid_rr_actual"

    if not math.isfinite(request.max_loss) or request.max_loss <= 0.0:
        return False, "invalid_max_loss"

    if not request.symbol.strip():
        return False, "missing_symbol"
    if not request.structure_type.strip():
        return False, "missing_structure_type"
    if not request.expiry.strip():
        return False, "missing_expiry"

    if not math.isfinite(request.debit_or_credit) or request.debit_or_credit <= 0.0:
        return False, "invalid_debit_or_credit"

    return True, "mcp_paper_transport_allowed"
