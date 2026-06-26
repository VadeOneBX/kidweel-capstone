"""Required fields, leg payload validation, and paper-payload conversion."""

from __future__ import annotations

import math
from typing import Any

from qops.bridge.chain_snapshot_export import parse_occ_us_option_contract
from qops.execution.paper_payload_candidate import PaperPayloadCandidate
from qops.guardrails.base import (
    STATUS_MALFORMED_PAYLOAD,
    STATUS_MISSING_REQUIRED_FIELD,
    GuardrailCandidate,
    GuardrailResult,
)

_ALLOWED_SIDES = frozenset({"buy", "sell", "BUY", "SELL"})
_ALLOWED_OPTION_TYPES = frozenset({"CALL", "PUT", "call", "put", "C", "P"})


def _normalize_option_type(raw: object) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip().upper()
    if text in {"CALL", "C"}:
        return "CALL"
    if text in {"PUT", "P"}:
        return "PUT"
    return None


def check_required_fields(candidate: GuardrailCandidate) -> GuardrailResult:
    missing: list[str] = []
    if not (candidate.candidate_id or "").strip():
        missing.append("candidate_id")
    if not (candidate.symbol or "").strip():
        missing.append("symbol")
    if not (candidate.structure or "").strip():
        missing.append("structure")
    if not candidate.legs:
        missing.append("legs")
    if candidate.max_loss is None:
        missing.append("max_loss")
    if missing:
        return GuardrailResult.reject(
            status=STATUS_MISSING_REQUIRED_FIELD,
            reason_code=STATUS_MISSING_REQUIRED_FIELD,
            message="missing_required_candidate_fields",
            details={"missing": missing},
        )
    return GuardrailResult.pass_(message="required_fields_present")


def check_leg_payload(candidate: GuardrailCandidate) -> GuardrailResult:
    for index, leg in enumerate(candidate.legs):
        if not isinstance(leg, dict):
            return GuardrailResult.reject(
                status=STATUS_MALFORMED_PAYLOAD,
                reason_code=STATUS_MALFORMED_PAYLOAD,
                message="leg_must_be_object",
                details={"leg_index": index},
            )
        side = leg.get("side")
        if side is None or str(side).strip() not in _ALLOWED_SIDES:
            return GuardrailResult.reject(
                status=STATUS_MALFORMED_PAYLOAD,
                reason_code=STATUS_MALFORMED_PAYLOAD,
                message="invalid_leg_side",
                details={"leg_index": index, "side": side},
            )
        option_type = _normalize_option_type(leg.get("option_type"))
        if option_type is None:
            return GuardrailResult.reject(
                status=STATUS_MALFORMED_PAYLOAD,
                reason_code=STATUS_MALFORMED_PAYLOAD,
                message="invalid_leg_option_type",
                details={"leg_index": index, "option_type": leg.get("option_type")},
            )
        strike = leg.get("strike")
        if strike is None or not math.isfinite(float(strike)) or float(strike) <= 0.0:
            return GuardrailResult.reject(
                status=STATUS_MALFORMED_PAYLOAD,
                reason_code=STATUS_MALFORMED_PAYLOAD,
                message="invalid_leg_strike",
                details={"leg_index": index, "strike": strike},
            )
        expiration = leg.get("expiration")
        if expiration is None or not str(expiration).strip():
            return GuardrailResult.reject(
                status=STATUS_MALFORMED_PAYLOAD,
                reason_code=STATUS_MALFORMED_PAYLOAD,
                message="missing_leg_expiration",
                details={"leg_index": index},
            )
        quantity = leg.get("quantity")
        if quantity is None:
            quantity = leg.get("qty")
        if quantity is None or not math.isfinite(float(quantity)) or float(quantity) <= 0.0:
            return GuardrailResult.reject(
                status=STATUS_MALFORMED_PAYLOAD,
                reason_code=STATUS_MALFORMED_PAYLOAD,
                message="invalid_leg_quantity",
                details={"leg_index": index, "quantity": quantity},
            )
    return GuardrailResult.pass_(message="legs_well_formed")


def _leg_from_occ_symbol(
    *,
    contract_symbol: str,
    side: str,
    quantity: int | float,
) -> dict[str, Any]:
    expiration, strike, option_type = parse_occ_us_option_contract(contract_symbol)
    return {
        "side": side,
        "option_type": option_type.upper(),
        "strike": strike,
        "expiration": expiration,
        "quantity": quantity,
    }


def guardrail_candidate_from_paper_payload(
    payload: PaperPayloadCandidate,
    *,
    watch_promotion_viable: bool = False,
    paper_only: bool = True,
    account_mode_paper: bool = True,
) -> GuardrailCandidate:
    legs: list[dict[str, Any]] = []
    if payload.long_leg_symbol:
        legs.append(
            _leg_from_occ_symbol(
                contract_symbol=payload.long_leg_symbol,
                side=payload.long_leg_side or "buy",
                quantity=payload.long_leg_qty or payload.qty or 1,
            )
        )
    if payload.short_leg_symbol:
        legs.append(
            _leg_from_occ_symbol(
                contract_symbol=payload.short_leg_symbol,
                side=payload.short_leg_side or "sell",
                quantity=payload.short_leg_qty or payload.qty or 1,
            )
        )

    watch = watch_promotion_viable
    if not watch and payload.approval_status and "WATCH" in payload.approval_status.upper():
        watch = True

    return GuardrailCandidate(
        candidate_id=payload.payload_id,
        symbol=payload.symbol,
        structure=payload.structure_type,
        legs=legs,
        max_loss=payload.max_loss,
        max_profit=payload.max_profit,
        rr_actual=payload.reward_risk,
        pmp=payload.pmp,
        ev=payload.expected_value,
        paper_only=paper_only,
        account_mode_paper=account_mode_paper,
        watch_promotion_viable=watch,
    )
