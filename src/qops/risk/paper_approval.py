"""Deterministic paper approval layer from math-gated spread candidates (no execution/MCP)."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Literal

import pandas as pd

from qops.risk.pmp_policy import min_rr_for_pmp
from qops.schemas.playbook import AllowedPlaybook

PROVENANCE_TAG = "approval_c1_paper_review"
DEFAULT_MAX_RISK_PER_CANDIDATE = 600.0

ApprovalStatus = Literal["APPROVED_FOR_PAPER_REVIEW", "REJECTED", "INCOMPLETE"]

_CANONICAL_STRUCTURES = frozenset(
    {
        AllowedPlaybook.BULL_CALL_SPREAD.value,
        AllowedPlaybook.BEAR_PUT_SPREAD.value,
        AllowedPlaybook.BULL_PUT_CREDIT_SPREAD.value,
        AllowedPlaybook.BEAR_CALL_CREDIT_SPREAD.value,
    }
)


@dataclass(frozen=True, slots=True)
class SpreadCandidateInputRow:
    """One row from spread_candidates.csv (STRUCT-C2 output)."""

    structure_type: str
    underlying_symbol: str
    trade_date: str
    expiration: str
    long_option_symbol: str
    short_option_symbol: str
    spread_width: float | None
    net_debit_or_credit: float | None
    pmp_for_gate: float | None
    pmp_source: str
    pmp_confidence: str
    max_profit: float | None
    max_loss: float | None
    reward_risk: float | None
    break_even: float | None
    capital_at_risk: float | None
    passes_spread_math_gate: bool
    probability_status: str
    ev_status: str
    candidate_pass: bool
    failure_reasons: str
    provenance: str


@dataclass(frozen=True, slots=True)
class PaperApprovalCandidate:
    approval_id: str
    symbol: str
    trade_date: str
    structure_type: str
    long_leg_symbol: str
    short_leg_symbol: str
    expiration: str
    spread_width: float | None
    net_debit_or_credit: float | None
    max_profit: float | None
    max_loss: float | None
    reward_risk: float | None
    pmp: float | None
    pmp_source: str
    pmp_confidence: str
    min_rr_required: float | None
    expected_value: float | None
    break_even: float | None
    capital_at_risk: float | None
    bid_ask_quality: str
    approval_status: ApprovalStatus
    approval_reason: str
    failure_reasons: str
    risk_unit: float | None
    suggested_contract_qty: int | None
    provenance: str


def _parse_bool(raw: object) -> bool:
    if isinstance(raw, bool):
        return raw
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return False
    return str(raw).strip().lower() in {"1", "true", "yes"}


def _parse_float(raw: object) -> float | None:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    try:
        out = float(raw)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _parse_str(raw: object, default: str = "") -> str:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return default
    return str(raw).strip()


def load_spread_candidate_rows(path: str | Path) -> list[SpreadCandidateInputRow]:
    p = Path(path)
    if not p.is_file():
        return []
    df = pd.read_csv(p)
    out: list[SpreadCandidateInputRow] = []
    for _, series in df.iterrows():
        pmp = _parse_float(series.get("pmp_for_gate"))
        if pmp is None:
            pmp = _parse_float(series.get("probability_of_profit"))
        out.append(
            SpreadCandidateInputRow(
                structure_type=_parse_str(series.get("structure_type")),
                underlying_symbol=_parse_str(series.get("underlying_symbol")),
                trade_date=_parse_str(series.get("trade_date")),
                expiration=_parse_str(series.get("expiration")),
                long_option_symbol=_parse_str(series.get("long_option_symbol")),
                short_option_symbol=_parse_str(series.get("short_option_symbol")),
                spread_width=_parse_float(series.get("spread_width")),
                net_debit_or_credit=_parse_float(series.get("net_debit_or_credit")),
                pmp_for_gate=pmp,
                pmp_source=_parse_str(series.get("pmp_source"), "missing"),
                pmp_confidence=_parse_str(series.get("pmp_confidence"), "MISSING"),
                max_profit=_parse_float(series.get("max_profit")),
                max_loss=_parse_float(series.get("max_loss")),
                reward_risk=_parse_float(series.get("reward_risk")),
                break_even=_parse_float(series.get("break_even")),
                capital_at_risk=_parse_float(series.get("capital_at_risk")),
                passes_spread_math_gate=_parse_bool(series.get("passes_spread_math_gate")),
                probability_status=_parse_str(series.get("probability_status")),
                ev_status=_parse_str(series.get("ev_status")),
                candidate_pass=_parse_bool(series.get("candidate_pass")),
                failure_reasons=_parse_str(series.get("failure_reasons")),
                provenance=_parse_str(series.get("provenance")),
            )
        )
    return out


def _approval_id(row: SpreadCandidateInputRow) -> str:
    key = "|".join(
        [
            row.underlying_symbol.upper(),
            row.trade_date,
            row.structure_type,
            row.long_option_symbol,
            row.short_option_symbol,
        ]
    )
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _expected_value(pmp: float, max_profit: float, max_loss: float) -> float:
    return pmp * max_profit - (1.0 - pmp) * max_loss


def evaluate_paper_approval(
    row: SpreadCandidateInputRow,
    *,
    max_risk: float,
) -> PaperApprovalCandidate:
    failures: list[str] = []
    approval_id = _approval_id(row)
    symbol = row.underlying_symbol.strip().upper()

    if not row.structure_type:
        failures.append("missing_structure_type")
    elif row.structure_type not in _CANONICAL_STRUCTURES:
        failures.append("unsupported_structure_type")

    if not symbol:
        failures.append("missing_symbol")
    if not row.long_option_symbol or not row.short_option_symbol:
        failures.append("missing_leg_symbols")

    pmp = row.pmp_for_gate
    if pmp is None:
        failures.append("missing_pmp")
    min_rr: float | None = None
    ev: float | None = None
    if pmp is not None:
        try:
            min_rr = min_rr_for_pmp(pmp)
        except ValueError:
            failures.append("pmp_outside_policy_table")
        if row.max_profit is not None and row.max_loss is not None and min_rr is not None:
            ev = _expected_value(pmp, row.max_profit, row.max_loss)

    if row.max_loss is None:
        failures.append("missing_max_loss")
    elif row.max_loss <= 0:
        failures.append("invalid_max_loss")

    if not row.candidate_pass:
        failures.append("not_candidate_pass")

    if not row.passes_spread_math_gate:
        failures.append("spread_math_gate_failed")

    if row.ev_status != "PASS":
        failures.append("ev_gate_not_pass")

    if row.probability_status != "PASS":
        failures.append("probability_gate_not_pass")

    if row.reward_risk is not None and min_rr is not None and row.reward_risk < min_rr:
        failures.append("insufficient_reward_risk_for_pmp")

    if ev is not None and ev <= 0:
        failures.append("non_positive_expected_value")

    risk_unit = row.max_loss if row.max_loss is not None and row.max_loss > 0 else None
    suggested_qty: int | None = None
    if risk_unit is not None and risk_unit > max_risk:
        failures.append("max_loss_exceeds_max_risk")

    bid_ask_quality = "PASS" if row.candidate_pass and not any(
        r in row.failure_reasons for r in ("invalid", "liquidity", "bid", "ask")
    ) else "UNKNOWN"

    if failures:
        if any(
            f in failures
            for f in (
                "missing_pmp",
                "missing_max_loss",
                "missing_structure_type",
                "missing_symbol",
                "missing_leg_symbols",
            )
        ):
            status: ApprovalStatus = "INCOMPLETE"
            reason = "incomplete_required_fields"
        else:
            status = "REJECTED"
            reason = failures[0]
    else:
        status = "APPROVED_FOR_PAPER_REVIEW"
        reason = "spread_math_and_pmp_gates_pass"
        suggested_qty = 1

    merged_failures = "|".join(dict.fromkeys([*failures, *filter(None, row.failure_reasons.split("|"))]))

    return PaperApprovalCandidate(
        approval_id=approval_id,
        symbol=symbol,
        trade_date=row.trade_date,
        structure_type=row.structure_type,
        long_leg_symbol=row.long_option_symbol,
        short_leg_symbol=row.short_option_symbol,
        expiration=row.expiration,
        spread_width=row.spread_width,
        net_debit_or_credit=row.net_debit_or_credit,
        max_profit=row.max_profit,
        max_loss=row.max_loss,
        reward_risk=row.reward_risk,
        pmp=pmp,
        pmp_source=row.pmp_source,
        pmp_confidence=row.pmp_confidence,
        min_rr_required=min_rr,
        expected_value=ev,
        break_even=row.break_even,
        capital_at_risk=row.capital_at_risk,
        bid_ask_quality=bid_ask_quality,
        approval_status=status,
        approval_reason=reason,
        failure_reasons=merged_failures,
        risk_unit=risk_unit,
        suggested_contract_qty=suggested_qty if status == "APPROVED_FOR_PAPER_REVIEW" else None,
        provenance=PROVENANCE_TAG,
    )


def build_paper_approval_candidates(
    rows: list[SpreadCandidateInputRow],
    *,
    max_risk: float = DEFAULT_MAX_RISK_PER_CANDIDATE,
    limit: int | None = None,
) -> list[PaperApprovalCandidate]:
    if max_risk <= 0 or not math.isfinite(max_risk):
        raise ValueError("max_risk must be positive and finite")
    out = [evaluate_paper_approval(row, max_risk=max_risk) for row in rows]
    if limit is not None and limit > 0:
        out = out[:limit]
    return out


def paper_approval_to_dataframe(candidates: list[PaperApprovalCandidate]) -> pd.DataFrame:
    if not candidates:
        return pd.DataFrame(columns=[f.name for f in fields(PaperApprovalCandidate)])
    return pd.DataFrame([{f.name: getattr(c, f.name) for f in fields(PaperApprovalCandidate)} for c in candidates])


def summarize_paper_approval(
    input_count: int,
    candidates: list[PaperApprovalCandidate],
) -> dict[str, object]:
    approved = sum(1 for c in candidates if c.approval_status == "APPROVED_FOR_PAPER_REVIEW")
    rejected = sum(1 for c in candidates if c.approval_status == "REJECTED")
    incomplete = sum(1 for c in candidates if c.approval_status == "INCOMPLETE")
    max_losses = [c.max_loss for c in candidates if c.max_loss is not None]
    pmp_sources: dict[str, int] = {}
    pmp_conf: dict[str, int] = {}
    for c in candidates:
        pmp_sources[c.pmp_source] = pmp_sources.get(c.pmp_source, 0) + 1
        pmp_conf[c.pmp_confidence] = pmp_conf.get(c.pmp_confidence, 0) + 1
    return {
        "input_spread_candidates": input_count,
        "approved_for_paper_review_count": approved,
        "rejected_count": rejected,
        "incomplete_count": incomplete,
        "max_loss_min": min(max_losses) if max_losses else None,
        "max_loss_max": max(max_losses) if max_losses else None,
        "max_loss_mean": sum(max_losses) / len(max_losses) if max_losses else None,
        "pmp_source_counts": pmp_sources,
        "pmp_confidence_counts": pmp_conf,
    }


def summarize_paper_approval_with_pass_count(
    rows: list[SpreadCandidateInputRow],
    candidates: list[PaperApprovalCandidate],
) -> dict[str, object]:
    base = summarize_paper_approval(len(rows), candidates)
    base["candidate_pass_input_rows"] = sum(1 for r in rows if r.candidate_pass)
    return base
