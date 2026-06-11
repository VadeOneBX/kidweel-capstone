"""Deterministic PMP proxy for spread math (short-leg delta); no ML/Claude authority."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from qops.risk.pmp_policy import validate_pmp
from qops.schemas.playbook import AllowedPlaybook

PmpProxyStatus = Literal[
    "AVAILABLE",
    "PMP_PROXY_AVAILABLE",
    "MISSING_INPUTS",
    "INVALID_INPUTS",
    "UNSUPPORTED_STRUCTURE",
    "OUTSIDE_POLICY_RANGE",
]

PmpProxySource = Literal[
    "vendor_probability",
    "short_leg_delta_proxy",
    "bsm_d2_proxy",
    "missing",
]

PmpProxyConfidence = Literal["HIGH", "MEDIUM", "LOW", "MISSING"]

_TABLE_MIN = 0.25
_TABLE_MAX = 0.90

_SUPPORTED = frozenset(
    {
        AllowedPlaybook.BULL_CALL_SPREAD.value,
        AllowedPlaybook.BEAR_PUT_SPREAD.value,
        AllowedPlaybook.BULL_PUT_CREDIT_SPREAD.value,
        AllowedPlaybook.BEAR_CALL_CREDIT_SPREAD.value,
    }
)


@dataclass(frozen=True, slots=True)
class SpreadPmpProxyInput:
    """Inputs for deterministic PMP proxy (short leg greeks only)."""

    structure_type: str
    short_leg_delta: float | None
    short_leg_greeks_source: str
    vendor_probability_of_profit: float | None = None


@dataclass(frozen=True, slots=True)
class PMPProxyResult:
    pmp: float | None
    pmp_source: PmpProxySource
    pmp_method: str
    pmp_status: PmpProxyStatus
    confidence: PmpProxyConfidence
    inputs_used: tuple[str, ...]
    failure_reasons: tuple[str, ...]


def _confidence_from_greeks_source(greeks_source: str) -> PmpProxyConfidence:
    src = greeks_source.strip().lower()
    if src == "alpaca_snapshot":
        return "MEDIUM"
    if src == "computed_bs":
        return "LOW"
    return "MISSING"


def _raw_delta_proxy_pmp(structure_type: str, short_leg_delta: float) -> float | None:
    if not math.isfinite(short_leg_delta):
        return None
    ad = abs(short_leg_delta)
    if structure_type in {
        AllowedPlaybook.BULL_CALL_SPREAD.value,
        AllowedPlaybook.BEAR_PUT_SPREAD.value,
    }:
        return ad
    if structure_type in {
        AllowedPlaybook.BULL_PUT_CREDIT_SPREAD.value,
        AllowedPlaybook.BEAR_CALL_CREDIT_SPREAD.value,
    }:
        return 1.0 - ad
    return None


def _in_table_range(pmp: float) -> bool:
    return _TABLE_MIN <= pmp <= _TABLE_MAX


def estimate_pmp_proxy(inputs: SpreadPmpProxyInput) -> PMPProxyResult:
    """
    Estimate PMP for spread math when vendor PMP is absent.

    Uses short-leg |delta| (or 1-|delta| for credit structures). Does not clamp
    into the Option Alpha table range.
    """
    if inputs.vendor_probability_of_profit is not None:
        try:
            validate_pmp(inputs.vendor_probability_of_profit)
        except ValueError:
            return PMPProxyResult(
                pmp=None,
                pmp_source="vendor_probability",
                pmp_method="vendor_probability",
                pmp_status="INVALID_INPUTS",
                confidence="HIGH",
                inputs_used=("vendor_probability_of_profit",),
                failure_reasons=("invalid_vendor_probability",),
            )
        p = inputs.vendor_probability_of_profit
        if not _in_table_range(p):
            return PMPProxyResult(
                pmp=None,
                pmp_source="vendor_probability",
                pmp_method="vendor_probability",
                pmp_status="OUTSIDE_POLICY_RANGE",
                confidence="HIGH",
                inputs_used=("vendor_probability_of_profit",),
                failure_reasons=("pmp_outside_supported_table",),
            )
        return PMPProxyResult(
            pmp=p,
            pmp_source="vendor_probability",
            pmp_method="vendor_probability",
            pmp_status="AVAILABLE",
            confidence="HIGH",
            inputs_used=("vendor_probability_of_profit",),
            failure_reasons=(),
        )

    st = inputs.structure_type.strip()
    if st not in _SUPPORTED:
        return PMPProxyResult(
            pmp=None,
            pmp_source="missing",
            pmp_method="none",
            pmp_status="UNSUPPORTED_STRUCTURE",
            confidence="MISSING",
            inputs_used=(),
            failure_reasons=("unsupported_structure_type",),
        )

    if inputs.short_leg_delta is None:
        return PMPProxyResult(
            pmp=None,
            pmp_source="missing",
            pmp_method="short_leg_delta_proxy",
            pmp_status="MISSING_INPUTS",
            confidence="MISSING",
            inputs_used=(),
            failure_reasons=("missing_short_leg_delta",),
        )

    conf = _confidence_from_greeks_source(inputs.short_leg_greeks_source)
    raw = _raw_delta_proxy_pmp(st, inputs.short_leg_delta)
    if raw is None:
        return PMPProxyResult(
            pmp=None,
            pmp_source="missing",
            pmp_method="short_leg_delta_proxy",
            pmp_status="INVALID_INPUTS",
            confidence=conf,
            inputs_used=("short_leg_delta", "structure_type"),
            failure_reasons=("invalid_short_leg_delta",),
        )

    try:
        validate_pmp(raw)
    except ValueError:
        return PMPProxyResult(
            pmp=None,
            pmp_source="short_leg_delta_proxy",
            pmp_method="short_leg_delta_proxy",
            pmp_status="INVALID_INPUTS",
            confidence=conf,
            inputs_used=("short_leg_delta", "structure_type"),
            failure_reasons=("pmp_not_open_unit_interval",),
        )

    if not _in_table_range(raw):
        return PMPProxyResult(
            pmp=None,
            pmp_source="short_leg_delta_proxy",
            pmp_method="short_leg_delta_proxy",
            pmp_status="OUTSIDE_POLICY_RANGE",
            confidence=conf,
            inputs_used=("short_leg_delta", "structure_type"),
            failure_reasons=("pmp_outside_supported_table",),
        )

    return PMPProxyResult(
        pmp=raw,
        pmp_source="short_leg_delta_proxy",
        pmp_method="short_leg_delta_proxy",
        pmp_status="PMP_PROXY_AVAILABLE",
        confidence=conf,
        inputs_used=("short_leg_delta", "structure_type", "short_leg_greeks_source"),
        failure_reasons=(),
    )
