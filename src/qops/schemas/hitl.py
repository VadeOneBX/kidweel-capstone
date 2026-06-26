"""Human-in-the-loop approval contract for paper transport (OPENAI-AGENTS-HITL-PAPER-TRANSPORT-C1)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

HITL_PACKET = "OPENAI-AGENTS-HITL-PAPER-TRANSPORT-C1"

ApprovalStatus = str
OperatorDecision = str | None

STATUS_APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
STATUS_APPROVED_BY_OPERATOR = "APPROVED_BY_OPERATOR"
STATUS_REJECTED_BY_OPERATOR = "REJECTED_BY_OPERATOR"
STATUS_WATCH_PENDING_REVIEW = "WATCH_PENDING_REVIEW"
STATUS_CLEAN_REJECT = "CLEAN_REJECT"
STATUS_PAPER_SUBMITTED = "PAPER_SUBMITTED"
STATUS_PAPER_SUBMIT_FAILED = "PAPER_SUBMIT_FAILED"
STATUS_LIVE_ENV_FORBIDDEN = "LIVE_ENV_FORBIDDEN"

DEFAULT_ACTION_WITHOUT_APPROVAL = "DO_NOT_SUBMIT"


@dataclass(slots=True)
class HitlApprovalItem:
    """Operator approval item for a paper transport candidate."""

    candidate_id: str
    symbol: str
    playbook: str | None
    structure: str
    legs: list[dict[str, Any]]
    max_profit: float | None
    max_loss: float
    rr_actual: float | None
    pmp: float | None
    ev: float | None
    gate_status: str
    approval_status: str
    operator_decision: str | None
    operator_reason: str | None
    paper_only: bool
    live_env_forbidden: bool
    created_at: str
    approved_at: str | None
    rejected_at: str | None
    trace_id: str | None
    source_artifacts: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise ValueError("hitl_invariant: paper_only must be True")
        if not self.live_env_forbidden:
            raise ValueError("hitl_invariant: live_env_forbidden must be True")

    def paper_submit_allowed(self) -> bool:
        return self.approval_status == STATUS_APPROVED_BY_OPERATOR

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HitlApprovalItem:
        return cls(
            candidate_id=str(data["candidate_id"]),
            symbol=str(data["symbol"]),
            playbook=data.get("playbook"),
            structure=str(data["structure"]),
            legs=list(data.get("legs") or []),
            max_profit=data.get("max_profit"),
            max_loss=float(data["max_loss"]),
            rr_actual=data.get("rr_actual"),
            pmp=data.get("pmp"),
            ev=data.get("ev"),
            gate_status=str(data.get("gate_status", "")),
            approval_status=str(data["approval_status"]),
            operator_decision=data.get("operator_decision"),
            operator_reason=data.get("operator_reason"),
            paper_only=bool(data.get("paper_only", True)),
            live_env_forbidden=bool(data.get("live_env_forbidden", True)),
            created_at=str(data["created_at"]),
            approved_at=data.get("approved_at"),
            rejected_at=data.get("rejected_at"),
            trace_id=data.get("trace_id"),
            source_artifacts=list(data.get("source_artifacts") or []),
        )
