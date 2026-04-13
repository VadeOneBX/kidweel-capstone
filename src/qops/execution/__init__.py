"""Paper-only execution boundary: payload, gate, audit (no broker, no network)."""

from __future__ import annotations

from qops.execution.audit import ExecutionAuditRecord, build_execution_audit
from qops.execution.gate import paper_execution_gate
from qops.execution.payload import ExecutionPayload, build_execution_payload

__all__ = [
    "ExecutionAuditRecord",
    "ExecutionPayload",
    "build_execution_audit",
    "build_execution_payload",
    "paper_execution_gate",
]
