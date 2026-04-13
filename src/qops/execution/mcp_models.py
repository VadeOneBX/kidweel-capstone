"""Typed MCP transport request/response scaffolding (paper-only; no I/O)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MCPExecutionRequest:
    """Narrow paper execution request shape for future Alpaca MCP transport."""

    symbol: str
    playbook: str
    structure_type: str
    expiry: str

    debit_or_credit: float
    max_profit: float
    max_loss: float

    rr_actual: float
    pmp: float

    tp_rule: str
    sl_rule: str
    time_exit_rule: str

    paper_only: bool


@dataclass(frozen=True, slots=True)
class MCPExecutionResponse:
    """Normalized MCP-like transport response for audit and downstream use."""

    accepted: bool
    status: str
    broker_mode: str
    external_order_id: str | None
    message: str
