"""Economics and WATCH boundary guardrails."""

from __future__ import annotations

import math

from qops.guardrails.base import (
    STATUS_EV_REJECTED,
    STATUS_INVALID_MAX_LOSS,
    STATUS_NEGATIVE_OR_ZERO_MAX_PROFIT,
    STATUS_RR_PMP_REJECTED,
    STATUS_WATCH_PENDING_REVIEW,
    GuardrailCandidate,
    GuardrailResult,
)


def check_economics(candidate: GuardrailCandidate) -> GuardrailResult:
    max_loss = candidate.max_loss
    if max_loss is None or not math.isfinite(max_loss) or max_loss <= 0.0:
        return GuardrailResult.reject(
            status=STATUS_INVALID_MAX_LOSS,
            reason_code=STATUS_INVALID_MAX_LOSS,
            message="max_loss_must_be_positive",
            details={"max_loss": max_loss},
        )

    max_profit = candidate.max_profit
    if max_profit is not None:
        if not math.isfinite(max_profit) or max_profit <= 0.0:
            return GuardrailResult.reject(
                status=STATUS_NEGATIVE_OR_ZERO_MAX_PROFIT,
                reason_code=STATUS_NEGATIVE_OR_ZERO_MAX_PROFIT,
                message="max_profit_must_be_positive_when_present",
                details={"max_profit": max_profit},
            )

    rr = candidate.rr_actual
    if rr is not None and (not math.isfinite(rr) or rr <= 0.0):
        return GuardrailResult.reject(
            status=STATUS_RR_PMP_REJECTED,
            reason_code=STATUS_RR_PMP_REJECTED,
            message="rr_actual_must_be_positive_when_present",
            details={"rr_actual": rr},
        )

    pmp = candidate.pmp
    if pmp is not None and (not math.isfinite(pmp) or not (0.0 < pmp < 1.0)):
        return GuardrailResult.reject(
            status=STATUS_RR_PMP_REJECTED,
            reason_code=STATUS_RR_PMP_REJECTED,
            message="pmp_must_be_in_open_unit_interval_when_present",
            details={"pmp": pmp},
        )

    ev = candidate.ev
    if ev is not None and (not math.isfinite(ev) or ev < 0.0):
        return GuardrailResult.reject(
            status=STATUS_EV_REJECTED,
            reason_code=STATUS_EV_REJECTED,
            message="ev_must_be_non_negative_when_present",
            details={"ev": ev},
        )

    return GuardrailResult.pass_(message="economics_ok")


def check_watch_boundary(candidate: GuardrailCandidate) -> GuardrailResult:
    if candidate.watch_promotion_viable:
        return GuardrailResult.reject(
            status=STATUS_WATCH_PENDING_REVIEW,
            reason_code=STATUS_WATCH_PENDING_REVIEW,
            message="watch_viable_operator_review_required",
            blocking=True,
            details={"watch_promotion_viable": True},
        )
    return GuardrailResult.pass_(message="ready_for_hitl_boundary")
