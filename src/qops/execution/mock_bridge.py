"""End-to-end deterministic mock MCP bridge (gate → mock transport → normalize → audit)."""

from __future__ import annotations

from qops.execution.audit import MCPBridgeAuditRecord, build_mcp_bridge_audit
from qops.execution.mcp_gate import mcp_paper_gate
from qops.execution.mcp_models import MCPExecutionRequest, MCPExecutionResponse
from qops.execution.mcp_response import normalize_mcp_response
from qops.execution.mock_transport import mock_mcp_transport


def run_mock_mcp_bridge(
    request: MCPExecutionRequest,
    *,
    mode: str = "accept",
) -> tuple[MCPExecutionResponse, MCPBridgeAuditRecord]:
    """
    Run the deterministic mock MCP bridge.

    Steps:
    - enforce mcp_paper_gate
    - call mock transport
    - normalize response
    - build audit-ready record

    Raises:
        ValueError: If mcp_paper_gate denies the request (no silent fallback to a reject response).
    """
    allowed, reason = mcp_paper_gate(request)
    if not allowed:
        raise ValueError(f"mcp_paper_gate denied: {reason}")

    raw = mock_mcp_transport(request, mode=mode)
    normalized = normalize_mcp_response(raw)
    audit = build_mcp_bridge_audit(request, normalized)
    return (normalized, audit)
