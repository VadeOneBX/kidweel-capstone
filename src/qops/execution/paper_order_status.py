"""Read-only post-submit paper order status audit (MCP-C12A-POST1)."""

from __future__ import annotations

import math
from dataclasses import dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

import pandas as pd

from qops.execution.alpaca_paper_bridge import (
    AlpacaPaperCredentials,
    resolve_alpaca_paper_credentials,
    validate_paper_endpoint,
)

@dataclass(frozen=True, slots=True)
class SubmittedTransportRow:
    payload_id: str
    approval_id: str
    external_order_id: str
    broker_mode: str
    previous_status: str
    submitted_at: str
    transport_status: str


@dataclass(frozen=True, slots=True)
class PaperOrderStatusAudit:
    payload_id: str
    approval_id: str
    external_order_id: str
    broker_mode: str
    previous_status: str
    current_status: str
    filled_qty: str
    filled_avg_price: str
    submitted_at: str
    checked_at: str
    status_message: str
    failure_reasons: str


class PaperOrderGetFn(Protocol):
    def __call__(
        self,
        credentials: AlpacaPaperCredentials,
        external_order_id: str,
    ) -> dict[str, object]: ...


def _parse_str(raw: object, default: str = "") -> str:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return default
    return str(raw).strip()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_paper_transport_results(path: str | Path) -> list[SubmittedTransportRow]:
    p = Path(path)
    if not p.is_file():
        return []
    df = pd.read_csv(p)
    out: list[SubmittedTransportRow] = []
    for _, series in df.iterrows():
        out.append(
            SubmittedTransportRow(
                payload_id=_parse_str(series.get("payload_id")),
                approval_id=_parse_str(series.get("approval_id")),
                external_order_id=_parse_str(series.get("external_order_id")),
                broker_mode=_parse_str(series.get("broker_mode"), "paper"),
                previous_status=_parse_str(series.get("status")),
                submitted_at=_parse_str(series.get("submitted_at")),
                transport_status=_parse_str(series.get("transport_status")),
            )
        )
    return out


def filter_submitted_transport_rows(
    rows: list[SubmittedTransportRow],
) -> list[SubmittedTransportRow]:
    filtered: list[SubmittedTransportRow] = []
    for row in rows:
        if row.transport_status != "PAPER_SUBMITTED":
            continue
        if not row.external_order_id:
            continue
        filtered.append(row)
    return filtered


def _order_field_str(raw: object) -> str:
    if raw is None:
        return ""
    if isinstance(raw, float) and (pd.isna(raw) or not math.isfinite(raw)):
        return ""
    if hasattr(raw, "value"):
        return str(raw.value)
    return str(raw)


def get_alpaca_paper_order_by_id(
    credentials: AlpacaPaperCredentials,
    external_order_id: str,
) -> dict[str, object]:
    """Fetch one order from Alpaca paper (read-only GET)."""
    endpoint_ok, detail = validate_paper_endpoint(credentials.base_url)
    if not endpoint_ok:
        return {
            "ok": False,
            "current_status": "",
            "filled_qty": "",
            "filled_avg_price": "",
            "status_message": detail,
            "failure_reasons": detail,
        }

    from alpaca.trading.client import TradingClient

    client = TradingClient(
        api_key=credentials.api_key,
        secret_key=credentials.secret_key,
        paper=True,
        url_override=credentials.base_url,
    )
    try:
        order = client.get_order_by_id(external_order_id)
    except Exception as exc:
        reason = f"alpaca_get_order_error:{type(exc).__name__}:{exc}"
        return {
            "ok": False,
            "current_status": "",
            "filled_qty": "",
            "filled_avg_price": "",
            "status_message": reason,
            "failure_reasons": reason,
        }

    status_str = _order_field_str(getattr(order, "status", None))
    return {
        "ok": True,
        "current_status": status_str,
        "filled_qty": _order_field_str(getattr(order, "filled_qty", None)),
        "filled_avg_price": _order_field_str(getattr(order, "filled_avg_price", None)),
        "status_message": f"order_status:{status_str}",
        "failure_reasons": "",
    }


def run_paper_order_status_audit(
    rows: list[SubmittedTransportRow],
    *,
    limit: int = 1,
    require_paper_endpoint: bool = True,
    get_order_fn: PaperOrderGetFn | None = None,
) -> tuple[list[PaperOrderStatusAudit], str | None]:
    """
    Audit paper order status for submitted transport rows.

    Returns (audit_rows, fatal_error). fatal_error is set when credentials fail closed.
    """
    submitted = filter_submitted_transport_rows(rows)
    if limit is not None and limit >= 0:
        submitted = submitted[:limit]

    if not submitted:
        return [], None

    credentials = resolve_alpaca_paper_credentials(require_paper_endpoint=require_paper_endpoint)
    if credentials is None:
        return [], "paper_credentials_not_ready"

    fetch = get_order_fn or get_alpaca_paper_order_by_id
    checked_at = _utc_now_iso()
    audits: list[PaperOrderStatusAudit] = []

    for row in submitted:
        raw = fetch(credentials, row.external_order_id)
        audits.append(
            PaperOrderStatusAudit(
                payload_id=row.payload_id,
                approval_id=row.approval_id,
                external_order_id=row.external_order_id,
                broker_mode=row.broker_mode,
                previous_status=row.previous_status,
                current_status=_parse_str(raw.get("current_status")),
                filled_qty=_parse_str(raw.get("filled_qty")),
                filled_avg_price=_parse_str(raw.get("filled_avg_price")),
                submitted_at=row.submitted_at,
                checked_at=checked_at,
                status_message=_parse_str(raw.get("status_message")),
                failure_reasons=_parse_str(raw.get("failure_reasons")),
            )
        )

    return audits, None


def paper_order_status_audit_to_dataframe(
    audits: list[PaperOrderStatusAudit],
) -> pd.DataFrame:
    if not audits:
        return pd.DataFrame(columns=[f.name for f in fields(PaperOrderStatusAudit)])
    return pd.DataFrame(
        [{f.name: getattr(a, f.name) for f in fields(PaperOrderStatusAudit)} for a in audits]
    )


def summarize_paper_order_status_audit(
    input_rows: list[SubmittedTransportRow],
    audits: list[PaperOrderStatusAudit],
) -> dict[str, object]:
    submitted = filter_submitted_transport_rows(input_rows)
    return {
        "input_transport_rows": len(input_rows),
        "submitted_orders_found": len(submitted),
        "status_checks_attempted": len(audits),
    }
