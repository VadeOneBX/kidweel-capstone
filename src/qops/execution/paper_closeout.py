"""Controlled paper mleg closeout after verified fills (CLOSE-C1)."""

from __future__ import annotations

import math
from dataclasses import dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Protocol

import pandas as pd

from qops.execution.alpaca_paper_bridge import (
    AlpacaPaperCredentials,
    alpaca_order_to_transport_raw,
    load_paper_payload_rows,
    resolve_alpaca_paper_credentials,
    sanitize_alpaca_mleg_order_request,
    transport_error_raw,
    validate_paper_endpoint,
)
from qops.execution.mcp_response import normalize_mcp_response
from qops.execution.paper_payload_candidate import PaperPayloadCandidate
from qops.execution.paper_position_audit import (
    BrokerPositionSnapshot,
    FilledOrderAuditInput,
    audit_one_filled_order,
    get_alpaca_paper_positions,
)
from qops.execution.spread_close_pricing import (
    ClosePriceSource,
    SpreadClosePricingResult,
    price_spread_close,
)

CloseStatus = Literal[
    "PAPER_CLOSE_DRY_RUN_READY",
    "PAPER_CLOSE_SUBMITTED",
    "PAPER_CLOSE_REJECTED",
    "PAPER_CLOSE_SKIPPED",
    "PAPER_CLOSE_ERROR",
]

from qops.schemas.playbook import AllowedPlaybook

PROVENANCE_TAG = "close_c1_paper_closeout"
QUOTE_BASED_CLOSE_PRICE_IMPLEMENTED = True
DEFAULT_CLOSEOUT_RESULTS_PATH = Path("data/processed/paper_closeout_results.csv")

_CREDIT_STRUCTURES = frozenset(
    {
        AllowedPlaybook.BULL_PUT_CREDIT_SPREAD.value,
        AllowedPlaybook.BEAR_CALL_CREDIT_SPREAD.value,
    }
)

_CANONICAL_STRUCTURES = frozenset(
    {
        AllowedPlaybook.BULL_CALL_SPREAD.value,
        AllowedPlaybook.BEAR_PUT_SPREAD.value,
        AllowedPlaybook.BULL_PUT_CREDIT_SPREAD.value,
        AllowedPlaybook.BEAR_CALL_CREDIT_SPREAD.value,
    }
)


@dataclass(frozen=True, slots=True)
class FilledOrderStatusRow:
    payload_id: str
    approval_id: str
    external_order_id: str
    current_status: str
    filled_qty: str
    filled_avg_price: str
    failure_reasons: str


@dataclass(frozen=True, slots=True)
class PaperCloseoutResult:
    payload_id: str
    approval_id: str
    original_external_order_id: str
    close_external_order_id: str | None
    symbol: str
    structure_type: str
    close_status: CloseStatus
    dry_run: bool
    broker_mode: str
    accepted: bool
    status: str
    message: str
    submitted_at: str | None
    failure_reasons: str
    provenance: str


class PaperCloseSubmitFn(Protocol):
    def __call__(
        self,
        credentials: AlpacaPaperCredentials,
        request: object,
    ) -> dict: ...


def _parse_str(raw: object, default: str = "") -> str:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return default
    return str(raw).strip()


def _parse_float(raw: object) -> float | None:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    try:
        out = float(raw)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) and out > 0 else None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def deterministic_close_client_order_id(payload_id: str, *, attempt: int = 1) -> str:
    if not payload_id:
        raise ValueError("payload_id required for close client_order_id")
    if attempt < 1:
        raise ValueError("close attempt must be >= 1")
    base = f"qops-paper-close-{payload_id}"
    if attempt == 1:
        return base[:48]
    return f"{base}-a{attempt}"[:48]


def count_prior_closeout_attempts(path: Path, payload_id: str) -> int:
    """Count prior closeout result rows for payload (each submit/reject writes one row)."""
    if not payload_id or not path.is_file():
        return 0
    df = pd.read_csv(path)
    count = 0
    for _, series in df.iterrows():
        if _parse_str(series.get("payload_id")) == payload_id:
            count += 1
    return count


def resolve_close_client_order_attempt(
    payload_id: str,
    *,
    results_path: Path = DEFAULT_CLOSEOUT_RESULTS_PATH,
    explicit_attempt: int | None = None,
) -> int:
    if explicit_attempt is not None:
        if explicit_attempt < 1:
            raise ValueError("close_attempt must be >= 1")
        return explicit_attempt
    return count_prior_closeout_attempts(results_path, payload_id) + 1


def load_paper_order_status_audit_rows(path: str | Path) -> list[FilledOrderStatusRow]:
    p = Path(path)
    if not p.is_file():
        return []
    df = pd.read_csv(p)
    out: list[FilledOrderStatusRow] = []
    for _, series in df.iterrows():
        out.append(
            FilledOrderStatusRow(
                payload_id=_parse_str(series.get("payload_id")),
                approval_id=_parse_str(series.get("approval_id")),
                external_order_id=_parse_str(series.get("external_order_id")),
                current_status=_parse_str(series.get("current_status")),
                filled_qty=_parse_str(series.get("filled_qty")),
                filled_avg_price=_parse_str(series.get("filled_avg_price")),
                failure_reasons=_parse_str(series.get("failure_reasons")),
            )
        )
    return out


def filter_filled_order_status_rows(
    rows: list[FilledOrderStatusRow],
    *,
    payload_id: str | None = None,
) -> list[FilledOrderStatusRow]:
    filtered: list[FilledOrderStatusRow] = []
    for row in rows:
        if payload_id and row.payload_id != payload_id:
            continue
        if row.current_status.lower() != "filled":
            continue
        if not row.external_order_id:
            continue
        if row.failure_reasons:
            continue
        filtered.append(row)
    return filtered


def _payload_index(rows: list[PaperPayloadCandidate]) -> dict[str, PaperPayloadCandidate]:
    return {row.payload_id: row for row in rows if row.payload_id}


def filled_order_audit_input_for_close(
    status: FilledOrderStatusRow,
    payload: PaperPayloadCandidate,
) -> FilledOrderAuditInput:
    long_qty = payload.long_leg_qty
    short_qty = payload.short_leg_qty
    if long_qty is None and payload.qty is not None:
        long_qty = payload.qty
    if short_qty is None and payload.qty is not None:
        short_qty = payload.qty
    return FilledOrderAuditInput(
        payload_id=status.payload_id,
        approval_id=status.approval_id or payload.approval_id,
        external_order_id=status.external_order_id,
        symbol=payload.symbol,
        structure_type=payload.structure_type,
        expected_long_leg_symbol=payload.long_leg_symbol,
        expected_short_leg_symbol=payload.short_leg_symbol,
        expected_long_leg_qty=long_qty,
        expected_short_leg_qty=short_qty,
    )


def _positions_by_symbol(
    snapshots: list[BrokerPositionSnapshot],
) -> dict[str, BrokerPositionSnapshot]:
    out: dict[str, BrokerPositionSnapshot] = {}
    for snap in snapshots:
        if snap.symbol:
            out[snap.symbol] = snap
    return out


def _pricing_message(pricing: SpreadClosePricingResult) -> str:
    return (
        f"close_price_source:{pricing.close_price_source};"
        f"close_price_status:{pricing.close_price_status}"
    )


def resolve_spread_close_pricing(
    payload: PaperPayloadCandidate,
    *,
    price_source: ClosePriceSource = "quote_mid",
    explicit_limit_price: float | None = None,
    quote_fetch_fn=None,
) -> SpreadClosePricingResult:
    return price_spread_close(
        payload,
        price_source=price_source,
        explicit_limit_price=explicit_limit_price,
        quote_fetch_fn=quote_fetch_fn,
    )


def _close_position_intent_for_leg_side(side: object) -> object:
    from alpaca.trading.enums import OrderSide, PositionIntent

    if side == OrderSide.SELL:
        return PositionIntent.SELL_TO_CLOSE
    return PositionIntent.BUY_TO_CLOSE


def _close_parent_side(structure_type: str):
    from alpaca.trading.enums import OrderSide

    if structure_type in _CREDIT_STRUCTURES:
        return OrderSide.BUY
    return OrderSide.SELL


def _alpaca_close_net_limit_price(structure_type: str, limit_price: float) -> float:
    if structure_type in _CREDIT_STRUCTURES:
        return abs(limit_price)
    return -abs(limit_price)


def build_alpaca_close_mleg_order_request(
    payload: PaperPayloadCandidate,
    *,
    limit_price: float,
    payload_id: str | None = None,
    close_attempt: int = 1,
):
    """Build multileg limit close order (option legs only, no parent equity symbol)."""
    from alpaca.trading.enums import OrderClass, OrderSide, OrderType, TimeInForce
    from alpaca.trading.requests import LimitOrderRequest, OptionLegRequest

    pid = payload_id or payload.payload_id
    if payload.qty is None or payload.qty <= 0:
        raise ValueError("payload.qty must be positive")
    if limit_price <= 0:
        raise ValueError("close limit_price must be positive")
    if payload.structure_type not in _CANONICAL_STRUCTURES:
        raise ValueError("unsupported_structure_type")
    if not payload.long_leg_symbol or not payload.short_leg_symbol:
        raise ValueError("payload leg symbols required")
    if payload.long_leg_qty is None or payload.short_leg_qty is None:
        raise ValueError("payload leg qty required")

    long_close_side = OrderSide.SELL
    short_close_side = OrderSide.BUY
    legs = [
        OptionLegRequest(
            symbol=payload.long_leg_symbol,
            ratio_qty=float(payload.long_leg_qty),
            side=long_close_side,
            position_intent=_close_position_intent_for_leg_side(long_close_side),
        ),
        OptionLegRequest(
            symbol=payload.short_leg_symbol,
            ratio_qty=float(payload.short_leg_qty),
            side=short_close_side,
            position_intent=_close_position_intent_for_leg_side(short_close_side),
        ),
    ]
    return LimitOrderRequest(
        symbol=None,
        qty=float(payload.qty),
        side=_close_parent_side(payload.structure_type),
        type=OrderType.LIMIT,
        time_in_force=TimeInForce.DAY,
        order_class=OrderClass.MLEG,
        legs=legs,
        limit_price=_alpaca_close_net_limit_price(payload.structure_type, limit_price),
        client_order_id=deterministic_close_client_order_id(pid, attempt=close_attempt),
    )


def submit_alpaca_paper_close_mleg_order(
    credentials: AlpacaPaperCredentials,
    request: object,
) -> dict:
    endpoint_ok, detail = validate_paper_endpoint(credentials.base_url)
    if not endpoint_ok:
        return transport_error_raw(detail)

    from alpaca.trading.client import TradingClient

    client = TradingClient(
        api_key=credentials.api_key,
        secret_key=credentials.secret_key,
        paper=True,
        url_override=credentials.base_url,
    )
    try:
        order = client.submit_order(order_data=request)
    except Exception as exc:
        return transport_error_raw(f"alpaca_close_submit_error:{type(exc).__name__}:{exc}")
    return alpaca_order_to_transport_raw(order, message_prefix="close_submitted")


def _skipped_result(
    *,
    status_row: FilledOrderStatusRow | None,
    payload: PaperPayloadCandidate | None,
    reason: str,
    message: str,
) -> PaperCloseoutResult:
    payload_id = status_row.payload_id if status_row else (payload.payload_id if payload else "")
    approval_id = status_row.approval_id if status_row else (payload.approval_id if payload else "")
    original_oid = status_row.external_order_id if status_row else ""
    symbol = payload.symbol if payload else ""
    structure = payload.structure_type if payload else ""
    return PaperCloseoutResult(
        payload_id=payload_id,
        approval_id=approval_id,
        original_external_order_id=original_oid,
        close_external_order_id=None,
        symbol=symbol,
        structure_type=structure,
        close_status="PAPER_CLOSE_SKIPPED",
        dry_run=True,
        broker_mode="paper",
        accepted=False,
        status="skipped",
        message=message,
        submitted_at=None,
        failure_reasons=reason,
        provenance=PROVENANCE_TAG,
    )


def _error_result(
    *,
    status_row: FilledOrderStatusRow,
    payload: PaperPayloadCandidate,
    reason: str,
    message: str,
    dry_run: bool,
) -> PaperCloseoutResult:
    return PaperCloseoutResult(
        payload_id=status_row.payload_id,
        approval_id=status_row.approval_id,
        original_external_order_id=status_row.external_order_id,
        close_external_order_id=None,
        symbol=payload.symbol,
        structure_type=payload.structure_type,
        close_status="PAPER_CLOSE_ERROR",
        dry_run=dry_run,
        broker_mode="paper",
        accepted=False,
        status="close_error",
        message=message,
        submitted_at=None,
        failure_reasons=reason,
        provenance=PROVENANCE_TAG,
    )


def run_paper_closeout(
    status_rows: list[FilledOrderStatusRow],
    payload_rows: list[PaperPayloadCandidate],
    *,
    payload_id: str | None = None,
    limit: int = 1,
    close_paper: bool = False,
    limit_price: float | None = None,
    price_source: ClosePriceSource = "quote_mid",
    require_paper_endpoint: bool = True,
    get_positions_fn=None,
    quote_fetch_fn=None,
    submit_close_fn: PaperCloseSubmitFn | None = None,
    close_results_path: Path = DEFAULT_CLOSEOUT_RESULTS_PATH,
    close_attempt: int | None = None,
) -> tuple[list[PaperCloseoutResult], str | None]:
    filled = filter_filled_order_status_rows(status_rows, payload_id=payload_id)
    if limit is not None and limit >= 0:
        filled = filled[:limit]

    if not filled:
        return [], None

    payloads = _payload_index(payload_rows)
    results: list[PaperCloseoutResult] = []

    credentials: AlpacaPaperCredentials | None = None
    if close_paper:
        credentials = resolve_alpaca_paper_credentials(require_paper_endpoint=require_paper_endpoint)
        if credentials is None:
            return [], "paper_credentials_not_ready"

    fetch_positions = get_positions_fn or get_alpaca_paper_positions
    position_raw: dict[str, object] | None = None
    position_index: dict[str, BrokerPositionSnapshot] = {}

    def ensure_positions() -> tuple[bool, str]:
        nonlocal position_raw, position_index, credentials
        if position_raw is not None:
            return bool(position_raw.get("ok")), _parse_str(position_raw.get("failure_reasons"))
        if credentials is None:
            credentials = resolve_alpaca_paper_credentials(require_paper_endpoint=require_paper_endpoint)
            if credentials is None:
                return False, "paper_credentials_not_ready"
        position_raw = fetch_positions(credentials)
        snapshots = position_raw.get("positions")
        if not isinstance(snapshots, list):
            snapshots = []
        position_index = _positions_by_symbol(snapshots)
        return bool(position_raw.get("ok")), _parse_str(position_raw.get("failure_reasons"))

    for status_row in filled:
        payload = payloads.get(status_row.payload_id)
        if payload is None:
            results.append(
                _skipped_result(
                    status_row=status_row,
                    payload=None,
                    reason="missing_payload_candidate",
                    message="payload_not_found",
                )
            )
            continue

        if payload.structure_type not in _CANONICAL_STRUCTURES:
            results.append(
                _skipped_result(
                    status_row=status_row,
                    payload=payload,
                    reason="unsupported_structure_type",
                    message="structure_not_supported_for_close",
                )
            )
            continue

        pos_ok, pos_failure = ensure_positions()
        audit_input = filled_order_audit_input_for_close(status_row, payload)
        position_audit = audit_one_filled_order(
            audit_input,
            position_index,
            fetch_ok=pos_ok,
            fetch_failure=pos_failure,
        )
        if position_audit.position_status != "POSITION_CONFIRMED":
            results.append(
                _error_result(
                    status_row=status_row,
                    payload=payload,
                    reason=position_audit.failure_reasons or "position_legs_not_confirmed",
                    message=f"position_verification:{position_audit.position_status}",
                    dry_run=not close_paper,
                )
            )
            continue

        pricing = resolve_spread_close_pricing(
            payload,
            price_source=price_source,
            explicit_limit_price=limit_price,
            quote_fetch_fn=quote_fetch_fn,
        )
        resolved_limit = pricing.suggested_close_limit

        if close_paper:
            if pricing.close_price_status == "MISSING_QUOTES":
                results.append(
                    _error_result(
                        status_row=status_row,
                        payload=payload,
                        reason=pricing.failure_reasons or "missing_quotes",
                        message="close_price_status:MISSING_QUOTES",
                        dry_run=False,
                    )
                )
                continue
            if resolved_limit is None:
                results.append(
                    _error_result(
                        status_row=status_row,
                        payload=payload,
                        reason=pricing.failure_reasons or "missing_close_limit_price",
                        message="close_price_status:MISSING",
                        dry_run=False,
                    )
                )
                continue

        if resolved_limit is None:
            results.append(
                _error_result(
                    status_row=status_row,
                    payload=payload,
                    reason=pricing.failure_reasons or "missing_close_limit_price_for_preview",
                    message=f"close_price_status:{pricing.close_price_status}",
                    dry_run=True,
                )
            )
            continue

        client_order_attempt = resolve_close_client_order_attempt(
            status_row.payload_id,
            results_path=close_results_path,
            explicit_attempt=close_attempt,
        )

        try:
            request = build_alpaca_close_mleg_order_request(
                payload,
                limit_price=resolved_limit,
                close_attempt=client_order_attempt,
            )
        except ValueError as exc:
            results.append(
                _error_result(
                    status_row=status_row,
                    payload=payload,
                    reason=str(exc),
                    message="close_request_build_failed",
                    dry_run=not close_paper,
                )
            )
            continue

        if not close_paper:
            results.append(
                PaperCloseoutResult(
                    payload_id=status_row.payload_id,
                    approval_id=status_row.approval_id,
                    original_external_order_id=status_row.external_order_id,
                    close_external_order_id=None,
                    symbol=payload.symbol,
                    structure_type=payload.structure_type,
                    close_status="PAPER_CLOSE_DRY_RUN_READY",
                    dry_run=True,
                    broker_mode="paper",
                    accepted=False,
                    status="dry_run",
                    message=(
                        f"{_pricing_message(pricing)};"
                        f"close_client_order_attempt:{client_order_attempt}"
                    ),
                    submitted_at=None,
                    failure_reasons="",
                    provenance=PROVENANCE_TAG,
                )
            )
            continue

        assert credentials is not None
        submit = submit_close_fn or submit_alpaca_paper_close_mleg_order
        submitted_at = _utc_now_iso()
        raw = submit(credentials, request)
        try:
            normalized = normalize_mcp_response(raw)
        except ValueError as exc:
            results.append(
                PaperCloseoutResult(
                    payload_id=status_row.payload_id,
                    approval_id=status_row.approval_id,
                    original_external_order_id=status_row.external_order_id,
                    close_external_order_id=None,
                    symbol=payload.symbol,
                    structure_type=payload.structure_type,
                    close_status="PAPER_CLOSE_ERROR",
                    dry_run=False,
                    broker_mode="paper",
                    accepted=False,
                    status="normalize_error",
                    message=str(exc),
                    submitted_at=submitted_at,
                    failure_reasons="normalize_mcp_response_failed",
                    provenance=PROVENANCE_TAG,
                )
            )
            continue

        close_status: CloseStatus = (
            "PAPER_CLOSE_SUBMITTED" if normalized.accepted else "PAPER_CLOSE_REJECTED"
        )
        results.append(
            PaperCloseoutResult(
                payload_id=status_row.payload_id,
                approval_id=status_row.approval_id,
                original_external_order_id=status_row.external_order_id,
                close_external_order_id=normalized.external_order_id,
                symbol=payload.symbol,
                structure_type=payload.structure_type,
                close_status=close_status,
                dry_run=False,
                broker_mode=normalized.broker_mode,
                accepted=normalized.accepted,
                status=normalized.status,
                message=normalized.message,
                submitted_at=submitted_at,
                failure_reasons="" if normalized.accepted else normalized.message,
                provenance=PROVENANCE_TAG,
            )
        )

    return results, None


def paper_closeout_to_dataframe(results: list[PaperCloseoutResult]) -> pd.DataFrame:
    if not results:
        return pd.DataFrame(columns=[f.name for f in fields(PaperCloseoutResult)])
    return pd.DataFrame(
        [{f.name: getattr(r, f.name) for f in fields(PaperCloseoutResult)} for r in results]
    )


def summarize_paper_closeout(
    status_rows: list[FilledOrderStatusRow],
    payload_rows: list[PaperPayloadCandidate],
    results: list[PaperCloseoutResult],
    *,
    payload_id: str | None = None,
) -> dict[str, object]:
    filled = filter_filled_order_status_rows(status_rows, payload_id=payload_id)
    payloads = _payload_index(payload_rows)
    matched = sum(1 for row in filled if row.payload_id in payloads)
    dry_ready = sum(1 for r in results if r.close_status == "PAPER_CLOSE_DRY_RUN_READY")
    return {
        "filled_orders_found": len(filled),
        "payload_rows_matched": matched,
        "close_results_count": len(results),
        "dry_run_ready_count": dry_ready,
    }
