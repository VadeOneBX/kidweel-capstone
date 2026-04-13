"""Lossless translation from execution payload to MCP request model (no network)."""

from __future__ import annotations

from qops.execution.mcp_models import MCPExecutionRequest
from qops.execution.payload import ExecutionPayload


def build_mcp_request(payload: ExecutionPayload) -> MCPExecutionRequest:
    """
    Translate an approved execution payload into an MCP execution request.

    Raises:
        ValueError: If the payload is not approved or cannot be translated without inference.
    """
    if not isinstance(payload, ExecutionPayload):
        raise TypeError("payload must be ExecutionPayload")
    if not payload.approved:
        raise ValueError("MCP request requires payload.approved is True")

    return MCPExecutionRequest(
        symbol=payload.symbol,
        playbook=payload.playbook,
        structure_type=payload.structure_type,
        expiry=payload.expiry,
        debit_or_credit=payload.debit_or_credit,
        max_profit=payload.max_profit,
        max_loss=payload.max_loss,
        rr_actual=payload.rr_actual,
        pmp=payload.pmp,
        tp_rule=payload.tp_rule,
        sl_rule=payload.sl_rule,
        time_exit_rule=payload.time_exit_rule,
        paper_only=True,
    )
