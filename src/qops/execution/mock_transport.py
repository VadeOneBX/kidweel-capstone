"""Deterministic offline mock MCP transport responses (no network, no broker)."""

from __future__ import annotations

from qops.execution.mcp_gate import mcp_paper_gate
from qops.execution.mcp_models import MCPExecutionRequest

_ALLOWED_MODES: frozenset[str] = frozenset({"accept", "reject"})


def mock_mcp_transport(
    request: MCPExecutionRequest,
    *,
    mode: str = "accept",
) -> dict:
    """
    Return a raw dict-shaped mock transport response.

    Modes:
    - "accept": return a paper accepted response if the request is valid per mcp_paper_gate.
    - "reject": return a paper rejected response if the request is valid per mcp_paper_gate.

    Raises:
        ValueError: If mode is not allowed, or if the request fails mcp_paper_gate (including
            when mode is "accept" so invalid requests are never silently coerced into rejections).
    """
    if mode not in _ALLOWED_MODES:
        raise ValueError(f"invalid mock transport mode: {mode!r}; allowed: {sorted(_ALLOWED_MODES)}")

    allowed, reason = mcp_paper_gate(request)
    if not allowed:
        raise ValueError(f"mcp_paper_gate denied mock transport: {reason}")

    if mode == "accept":
        return {
            "accepted": True,
            "status": "accepted",
            "broker_mode": "paper",
            "external_order_id": "mock-paper-0001",
            "message": "accepted by mock paper transport",
        }

    return {
        "accepted": False,
        "status": "rejected",
        "broker_mode": "paper",
        "external_order_id": None,
        "message": "rejected by mock paper transport",
    }
