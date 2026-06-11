"""Deterministic risk policy helpers for PMP, RR audit, exits, and approval."""

from __future__ import annotations

from qops.risk.approval import evaluate_trade_structure
from qops.risk.exits import debit_stop_loss, take_profit_target, time_exit_rule
from qops.risk.pmp_policy import (
    PMP_TO_MIN_RR,
    min_rr_for_pmp,
    normalize_pmp_bucket,
    passes_pmp_rr_gate,
    required_rr_from_pmp,
    validate_pmp,
)
from qops.risk.pmp_proxy import PMPProxyResult, SpreadPmpProxyInput, estimate_pmp_proxy
from qops.risk.paper_approval import (
    PaperApprovalCandidate,
    SpreadCandidateInputRow,
    build_paper_approval_candidates,
    evaluate_paper_approval,
    load_spread_candidate_rows,
)
from qops.risk.rr_audit import audit_structure_rr, rr_is_sufficient

__all__ = [
    "audit_structure_rr",
    "build_paper_approval_candidates",
    "debit_stop_loss",
    "estimate_pmp_proxy",
    "evaluate_paper_approval",
    "evaluate_trade_structure",
    "load_spread_candidate_rows",
    "PaperApprovalCandidate",
    "PMPProxyResult",
    "PMP_TO_MIN_RR",
    "min_rr_for_pmp",
    "normalize_pmp_bucket",
    "passes_pmp_rr_gate",
    "required_rr_from_pmp",
    "rr_is_sufficient",
    "SpreadPmpProxyInput",
    "take_profit_target",
    "time_exit_rule",
    "validate_pmp",
]
