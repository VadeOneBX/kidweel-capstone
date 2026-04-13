"""Paper-only execution boundary: payload, gate, audit, MCP transport scaffolding (no broker, no network)."""

from __future__ import annotations

from qops.execution.audit import (
    ExecutionAuditRecord,
    MCPBridgeAuditRecord,
    build_execution_audit,
    build_mcp_bridge_audit,
)
from qops.execution.gate import paper_execution_gate
from qops.execution.mcp_adapter import build_mcp_request
from qops.execution.mcp_gate import mcp_paper_gate
from qops.execution.mcp_models import MCPExecutionRequest, MCPExecutionResponse
from qops.execution.mcp_response import normalize_mcp_response
from qops.execution.mock_bridge import run_mock_mcp_bridge
from qops.execution.mock_transport import mock_mcp_transport
from qops.execution.payload import ExecutionPayload, build_execution_payload

__all__ = [
    "ExecutionAuditRecord",
    "ExecutionPayload",
    "MCPBridgeAuditRecord",
    "MCPExecutionRequest",
    "MCPExecutionResponse",
    "build_execution_audit",
    "build_execution_payload",
    "build_mcp_bridge_audit",
    "build_mcp_request",
    "mcp_paper_gate",
    "mock_mcp_transport",
    "normalize_mcp_response",
    "paper_execution_gate",
    "run_mock_mcp_bridge",
]
