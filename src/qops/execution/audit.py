"""Immutable execution audit records (no I/O, no state)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from qops.execution.mcp_models import MCPExecutionRequest, MCPExecutionResponse
from qops.execution.payload import ExecutionPayload


@dataclass(frozen=True, slots=True)
class MCPBridgeAuditRecord:
    """Immutable audit snapshot for a mock MCP bridge run (request + normalized response)."""

    timestamp: str
    symbol: str
    playbook: str
    broker_mode: str
    status: str
    accepted: bool
    external_order_id: str | None
    message: str


@dataclass(frozen=True, slots=True)
class ExecutionAuditRecord:
    """Immutable audit snapshot for a constructed execution payload."""

    timestamp: str
    symbol: str
    playbook: str

    approved: bool
    approval_reason: str

    rr_actual: float
    pmp: float

    tp_rule: str
    sl_rule: str
    time_exit_rule: str


def build_execution_audit(payload: ExecutionPayload) -> ExecutionAuditRecord:
    """Build immutable audit record from execution payload."""
    if not isinstance(payload, ExecutionPayload):
        raise TypeError("payload must be ExecutionPayload")

    timestamp = datetime.now(timezone.utc).isoformat()

    return ExecutionAuditRecord(
        timestamp=timestamp,
        symbol=payload.symbol,
        playbook=payload.playbook,
        approved=payload.approved,
        approval_reason=payload.approval_reason,
        rr_actual=payload.rr_actual,
        pmp=payload.pmp,
        tp_rule=payload.tp_rule,
        sl_rule=payload.sl_rule,
        time_exit_rule=payload.time_exit_rule,
    )


def build_mcp_bridge_audit(
    request: MCPExecutionRequest,
    response: MCPExecutionResponse,
) -> MCPBridgeAuditRecord:
    """Build immutable mock-bridge audit record from request and normalized MCP response."""
    if not isinstance(request, MCPExecutionRequest):
        raise TypeError("request must be MCPExecutionRequest")
    if not isinstance(response, MCPExecutionResponse):
        raise TypeError("response must be MCPExecutionResponse")

    timestamp = datetime.now(timezone.utc).isoformat()

    return MCPBridgeAuditRecord(
        timestamp=timestamp,
        symbol=request.symbol,
        playbook=request.playbook,
        broker_mode=response.broker_mode,
        status=response.status,
        accepted=response.accepted,
        external_order_id=response.external_order_id,
        message=response.message,
    )
