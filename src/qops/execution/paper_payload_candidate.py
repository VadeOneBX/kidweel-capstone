"""Paper order payload candidates from APPROVED_FOR_PAPER_REVIEW rows (no MCP, no submission)."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Literal

import pandas as pd

from qops.schemas.playbook import AllowedPlaybook

PROVENANCE_TAG = "payload_c1_paper_candidate"
ORDER_CLASS_MLEG = "mleg"
ORDER_TYPE_LIMIT = "limit"
TIME_IN_FORCE_DAY = "day"

PayloadStatus = Literal["PAPER_PAYLOAD_READY", "REJECTED", "INCOMPLETE"]

_CANONICAL_STRUCTURES = frozenset(
    {
        AllowedPlaybook.BULL_CALL_SPREAD.value,
        AllowedPlaybook.BEAR_PUT_SPREAD.value,
        AllowedPlaybook.BULL_PUT_CREDIT_SPREAD.value,
        AllowedPlaybook.BEAR_CALL_CREDIT_SPREAD.value,
    }
)

_LEG_SIDES: dict[str, tuple[str, str]] = {
    AllowedPlaybook.BULL_CALL_SPREAD.value: ("buy", "sell"),
    AllowedPlaybook.BEAR_PUT_SPREAD.value: ("buy", "sell"),
    AllowedPlaybook.BULL_PUT_CREDIT_SPREAD.value: ("buy", "sell"),
    AllowedPlaybook.BEAR_CALL_CREDIT_SPREAD.value: ("buy", "sell"),
}


@dataclass(frozen=True, slots=True)
class PaperApprovalInputRow:
    """One row from paper_approval_candidates.csv (APPROVAL-C1 output)."""

    approval_id: str
    symbol: str
    trade_date: str
    structure_type: str
    long_leg_symbol: str
    short_leg_symbol: str
    expiration: str
    net_debit_or_credit: float | None
    max_profit: float | None
    max_loss: float | None
    reward_risk: float | None
    pmp: float | None
    pmp_source: str
    pmp_confidence: str
    expected_value: float | None
    approval_status: str
    failure_reasons: str
    suggested_contract_qty: int | None
    provenance: str


@dataclass(frozen=True, slots=True)
class PaperPayloadCandidate:
    payload_id: str
    approval_id: str
    symbol: str
    trade_date: str
    structure_type: str
    order_class: str
    order_type: str
    time_in_force: str
    qty: int | None
    limit_price: float | None
    max_loss: float | None
    max_profit: float | None
    reward_risk: float | None
    pmp: float | None
    pmp_source: str
    pmp_confidence: str
    expected_value: float | None
    long_leg_symbol: str
    short_leg_symbol: str
    long_leg_side: str
    short_leg_side: str
    long_leg_qty: int | None
    short_leg_qty: int | None
    expiration: str
    approval_status: str
    payload_status: PayloadStatus
    payload_reason: str
    failure_reasons: str
    provenance: str


def _parse_float(raw: object) -> float | None:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    try:
        out = float(raw)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _parse_int(raw: object) -> int | None:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    try:
        out = int(float(raw))
    except (TypeError, ValueError):
        return None
    return out


def _parse_str(raw: object, default: str = "") -> str:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return default
    return str(raw).strip()


def load_paper_approval_rows(path: str | Path) -> list[PaperApprovalInputRow]:
    p = Path(path)
    if not p.is_file():
        return []
    df = pd.read_csv(p)
    out: list[PaperApprovalInputRow] = []
    for _, series in df.iterrows():
        out.append(
            PaperApprovalInputRow(
                approval_id=_parse_str(series.get("approval_id")),
                symbol=_parse_str(series.get("symbol")),
                trade_date=_parse_str(series.get("trade_date")),
                structure_type=_parse_str(series.get("structure_type")),
                long_leg_symbol=_parse_str(series.get("long_leg_symbol")),
                short_leg_symbol=_parse_str(series.get("short_leg_symbol")),
                expiration=_parse_str(series.get("expiration")),
                net_debit_or_credit=_parse_float(series.get("net_debit_or_credit")),
                max_profit=_parse_float(series.get("max_profit")),
                max_loss=_parse_float(series.get("max_loss")),
                reward_risk=_parse_float(series.get("reward_risk")),
                pmp=_parse_float(series.get("pmp")),
                pmp_source=_parse_str(series.get("pmp_source"), "missing"),
                pmp_confidence=_parse_str(series.get("pmp_confidence"), "MISSING"),
                expected_value=_parse_float(series.get("expected_value")),
                approval_status=_parse_str(series.get("approval_status")),
                failure_reasons=_parse_str(series.get("failure_reasons")),
                suggested_contract_qty=_parse_int(series.get("suggested_contract_qty")),
                provenance=_parse_str(series.get("provenance")),
            )
        )
    return out


def _payload_id(approval_id: str, structure_type: str, long_leg: str, short_leg: str) -> str:
    key = "|".join([approval_id, structure_type, long_leg, short_leg, PROVENANCE_TAG])
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _leg_sides(structure_type: str) -> tuple[str, str] | None:
    return _LEG_SIDES.get(structure_type)


def evaluate_paper_payload_candidate(row: PaperApprovalInputRow) -> PaperPayloadCandidate:
    failures: list[str] = []
    payload_id = _payload_id(
        row.approval_id or "",
        row.structure_type,
        row.long_leg_symbol,
        row.short_leg_symbol,
    )

    if row.approval_status != "APPROVED_FOR_PAPER_REVIEW":
        failures.append("approval_not_approved_for_paper_review")

    if not row.approval_id:
        failures.append("missing_approval_id")
    if not row.structure_type:
        failures.append("missing_structure_type")
    elif row.structure_type not in _CANONICAL_STRUCTURES:
        failures.append("unsupported_structure_type")

    if not row.long_leg_symbol or not row.short_leg_symbol:
        failures.append("missing_leg_symbols")

    qty = row.suggested_contract_qty
    if qty is None:
        failures.append("missing_suggested_contract_qty")
    elif qty <= 0:
        failures.append("invalid_suggested_contract_qty")

    max_loss = row.max_loss
    if max_loss is None:
        failures.append("missing_max_loss")
    elif max_loss <= 0:
        failures.append("invalid_max_loss")

    limit_price = row.net_debit_or_credit
    if limit_price is None:
        failures.append("missing_limit_price")
    elif limit_price <= 0:
        failures.append("invalid_limit_price")

    pmp = row.pmp
    if pmp is None:
        failures.append("missing_pmp")

    ev = row.expected_value
    if ev is None:
        failures.append("missing_expected_value")
    elif ev <= 0:
        failures.append("non_positive_expected_value")

    sides = _leg_sides(row.structure_type) if row.structure_type else None
    if sides is None and row.structure_type and row.structure_type in _CANONICAL_STRUCTURES:
        failures.append("leg_sides_undetermined")
    long_side, short_side = sides if sides else ("", "")

    if failures:
        incomplete_keys = {
            "missing_approval_id",
            "missing_structure_type",
            "missing_leg_symbols",
            "missing_suggested_contract_qty",
            "missing_max_loss",
            "missing_limit_price",
            "missing_pmp",
            "missing_expected_value",
        }
        if "approval_not_approved_for_paper_review" in failures:
            status: PayloadStatus = "REJECTED"
            reason = "approval_not_approved_for_paper_review"
        elif any(f in failures for f in incomplete_keys):
            status = "INCOMPLETE"
            reason = "incomplete_required_fields"
        else:
            status = "REJECTED"
            reason = failures[0]
        leg_qty: int | None = None
        order_qty: int | None = None
    else:
        status = "PAPER_PAYLOAD_READY"
        reason = "paper_payload_fields_valid"
        order_qty = qty
        leg_qty = qty

    merged = "|".join(dict.fromkeys([*failures, *filter(None, row.failure_reasons.split("|"))]))

    return PaperPayloadCandidate(
        payload_id=payload_id,
        approval_id=row.approval_id,
        symbol=row.symbol.strip().upper(),
        trade_date=row.trade_date,
        structure_type=row.structure_type,
        order_class=ORDER_CLASS_MLEG,
        order_type=ORDER_TYPE_LIMIT,
        time_in_force=TIME_IN_FORCE_DAY,
        qty=order_qty,
        limit_price=limit_price,
        max_loss=max_loss,
        max_profit=row.max_profit,
        reward_risk=row.reward_risk,
        pmp=pmp,
        pmp_source=row.pmp_source,
        pmp_confidence=row.pmp_confidence,
        expected_value=ev,
        long_leg_symbol=row.long_leg_symbol,
        short_leg_symbol=row.short_leg_symbol,
        long_leg_side=long_side,
        short_leg_side=short_side,
        long_leg_qty=leg_qty,
        short_leg_qty=leg_qty,
        expiration=row.expiration,
        approval_status=row.approval_status,
        payload_status=status,
        payload_reason=reason,
        failure_reasons=merged,
        provenance=PROVENANCE_TAG,
    )


def build_paper_payload_candidates(
    rows: list[PaperApprovalInputRow],
    *,
    limit: int | None = None,
) -> list[PaperPayloadCandidate]:
    out = [evaluate_paper_payload_candidate(row) for row in rows]
    if limit is not None and limit > 0:
        out = out[:limit]
    return out


def paper_payload_to_dataframe(candidates: list[PaperPayloadCandidate]) -> pd.DataFrame:
    if not candidates:
        return pd.DataFrame(columns=[f.name for f in fields(PaperPayloadCandidate)])
    return pd.DataFrame([{f.name: getattr(c, f.name) for f in fields(PaperPayloadCandidate)} for c in candidates])


def summarize_paper_payload_candidates(
    input_count: int,
    candidates: list[PaperPayloadCandidate],
) -> dict[str, object]:
    ready = sum(1 for c in candidates if c.payload_status == "PAPER_PAYLOAD_READY")
    rejected = sum(1 for c in candidates if c.payload_status == "REJECTED")
    incomplete = sum(1 for c in candidates if c.payload_status == "INCOMPLETE")
    approved_input = sum(1 for c in candidates if c.approval_status == "APPROVED_FOR_PAPER_REVIEW")
    structure_counts: dict[str, int] = {}
    for c in candidates:
        if c.payload_status == "PAPER_PAYLOAD_READY":
            structure_counts[c.structure_type] = structure_counts.get(c.structure_type, 0) + 1
    return {
        "input_approval_candidates": input_count,
        "approved_for_paper_review_input_rows": approved_input,
        "paper_payload_ready_count": ready,
        "rejected_count": rejected,
        "incomplete_count": incomplete,
        "structure_counts_ready": structure_counts,
    }
