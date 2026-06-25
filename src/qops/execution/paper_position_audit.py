"""Read-only paper position audit after filled mleg orders (POSITION-C1)."""

from __future__ import annotations

import math
from dataclasses import dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Protocol

import pandas as pd

from qops.execution.alpaca_paper_bridge import (
    AlpacaPaperCredentials,
    load_paper_payload_rows,
    resolve_alpaca_paper_credentials,
    validate_paper_endpoint,
)
from qops.execution.paper_payload_candidate import PaperPayloadCandidate

PROVENANCE_TAG = "position_c1_paper_position_audit"
DEFAULT_TRANSPORT_RESULTS_PATH = Path("data/processed/paper_transport_results.csv")
DEFAULT_PAYLOAD_CANDIDATES_PATH = Path("data/processed/paper_payload_candidates.csv")

PositionStatus = Literal[
    "POSITION_CONFIRMED",
    "POSITION_PARTIAL",
    "POSITION_NOT_FOUND",
    "POSITION_AUDIT_ERROR",
]

InputSource = Literal["status_audit", "transport"]


@dataclass(frozen=True, slots=True)
class FilledOrderAuditInput:
    payload_id: str
    approval_id: str
    external_order_id: str
    symbol: str
    structure_type: str
    expected_long_leg_symbol: str
    expected_short_leg_symbol: str
    expected_long_leg_qty: int | None
    expected_short_leg_qty: int | None


@dataclass(frozen=True, slots=True)
class PaperPositionAudit:
    payload_id: str
    approval_id: str
    external_order_id: str
    symbol: str
    structure_type: str
    expected_long_leg_symbol: str
    expected_short_leg_symbol: str
    long_leg_position_found: bool
    short_leg_position_found: bool
    long_leg_qty: str
    short_leg_qty: str
    position_status: PositionStatus
    checked_at: str
    failure_reasons: str
    provenance: str


@dataclass(frozen=True, slots=True)
class BrokerPositionSnapshot:
    symbol: str
    qty: str
    side: str


class PaperPositionsGetFn(Protocol):
    def __call__(
        self,
        credentials: AlpacaPaperCredentials,
    ) -> dict[str, object]: ...


def _parse_str(raw: object, default: str = "") -> str:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return default
    return str(raw).strip()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_filled_order_input_path(input_path: Path) -> tuple[InputSource, Path]:
    if input_path.is_file():
        return "status_audit", input_path
    return "transport", DEFAULT_TRANSPORT_RESULTS_PATH


def _load_transport_index(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    df = pd.read_csv(path)
    index: dict[str, dict[str, str]] = {}
    for _, series in df.iterrows():
        payload_id = _parse_str(series.get("payload_id"))
        if not payload_id:
            continue
        index[payload_id] = {
            "approval_id": _parse_str(series.get("approval_id")),
            "external_order_id": _parse_str(series.get("external_order_id")),
            "symbol": _parse_str(series.get("symbol")),
            "structure_type": _parse_str(series.get("structure_type")),
            "transport_status": _parse_str(series.get("transport_status")),
            "status": _parse_str(series.get("status")),
        }
    return index


def _payload_leg_index(rows: list[PaperPayloadCandidate]) -> dict[str, PaperPayloadCandidate]:
    return {row.payload_id: row for row in rows if row.payload_id}


def _build_filled_input(
    *,
    payload_id: str,
    approval_id: str,
    external_order_id: str,
    transport_row: dict[str, str] | None,
    payload_row: PaperPayloadCandidate | None,
) -> FilledOrderAuditInput:
    symbol = transport_row.get("symbol", "") if transport_row else ""
    structure_type = transport_row.get("structure_type", "") if transport_row else ""
    if payload_row is not None:
        symbol = payload_row.symbol or symbol
        structure_type = payload_row.structure_type or structure_type
    long_sym = payload_row.long_leg_symbol if payload_row else ""
    short_sym = payload_row.short_leg_symbol if payload_row else ""
    long_qty = payload_row.long_leg_qty if payload_row else None
    short_qty = payload_row.short_leg_qty if payload_row else None
    if long_qty is None and payload_row is not None and payload_row.qty is not None:
        long_qty = payload_row.qty
    if short_qty is None and payload_row is not None and payload_row.qty is not None:
        short_qty = payload_row.qty
    if approval_id == "" and transport_row:
        approval_id = transport_row.get("approval_id", "")
    if external_order_id == "" and transport_row:
        external_order_id = transport_row.get("external_order_id", "")
    return FilledOrderAuditInput(
        payload_id=payload_id,
        approval_id=approval_id,
        external_order_id=external_order_id,
        symbol=symbol,
        structure_type=structure_type,
        expected_long_leg_symbol=long_sym,
        expected_short_leg_symbol=short_sym,
        expected_long_leg_qty=long_qty,
        expected_short_leg_qty=short_qty,
    )


def load_filled_order_audit_inputs(
    input_path: Path,
    *,
    transport_path: Path = DEFAULT_TRANSPORT_RESULTS_PATH,
    payload_candidates_path: Path = DEFAULT_PAYLOAD_CANDIDATES_PATH,
) -> tuple[list[FilledOrderAuditInput], InputSource]:
    source, resolved = resolve_filled_order_input_path(input_path)
    transport_index = _load_transport_index(transport_path)
    payload_rows = load_paper_payload_rows(payload_candidates_path)
    payload_index = _payload_leg_index(payload_rows)

    if source == "transport" and not input_path.is_file():
        resolved = transport_path

    if not resolved.is_file():
        return [], source

    df = pd.read_csv(resolved)
    out: list[FilledOrderAuditInput] = []

    for _, series in df.iterrows():
        payload_id = _parse_str(series.get("payload_id"))
        if not payload_id:
            continue

        if source == "status_audit":
            current_status = _parse_str(series.get("current_status")).lower()
            if current_status != "filled":
                continue
            if _parse_str(series.get("failure_reasons")):
                continue
            approval_id = _parse_str(series.get("approval_id"))
            external_order_id = _parse_str(series.get("external_order_id"))
        else:
            transport_status = _parse_str(series.get("transport_status"))
            if transport_status != "PAPER_SUBMITTED":
                continue
            approval_id = _parse_str(series.get("approval_id"))
            external_order_id = _parse_str(series.get("external_order_id"))
            if not external_order_id:
                continue

        transport_row = transport_index.get(payload_id)
        if transport_row is None and source == "transport":
            transport_row = {
                "approval_id": approval_id,
                "external_order_id": external_order_id,
                "symbol": _parse_str(series.get("symbol")),
                "structure_type": _parse_str(series.get("structure_type")),
                "transport_status": transport_status,
                "status": _parse_str(series.get("status")),
            }

        out.append(
            _build_filled_input(
                payload_id=payload_id,
                approval_id=approval_id,
                external_order_id=external_order_id,
                transport_row=transport_row,
                payload_row=payload_index.get(payload_id),
            )
        )

    return out, source


def filter_filled_order_audit_inputs(
    rows: list[FilledOrderAuditInput],
) -> list[FilledOrderAuditInput]:
    return [row for row in rows if row.external_order_id]


def _position_side_str(raw: object) -> str:
    if raw is None:
        return ""
    if hasattr(raw, "value"):
        return str(raw.value)
    return str(raw).strip().lower()


def _position_qty_str(raw: object) -> str:
    if raw is None:
        return ""
    if isinstance(raw, float) and (pd.isna(raw) or not math.isfinite(raw)):
        return ""
    return str(raw)


def get_alpaca_paper_positions(
    credentials: AlpacaPaperCredentials,
) -> dict[str, object]:
    """Fetch all open paper positions (read-only GET)."""
    endpoint_ok, detail = validate_paper_endpoint(credentials.base_url)
    if not endpoint_ok:
        return {"ok": False, "positions": [], "failure_reasons": detail}

    from alpaca.trading.client import TradingClient

    client = TradingClient(
        api_key=credentials.api_key,
        secret_key=credentials.secret_key,
        paper=True,
        url_override=credentials.base_url,
    )
    try:
        raw_positions = client.get_all_positions()
    except Exception as exc:
        reason = f"alpaca_get_positions_error:{type(exc).__name__}:{exc}"
        return {"ok": False, "positions": [], "failure_reasons": reason}

    snapshots: list[BrokerPositionSnapshot] = []
    for position in raw_positions:
        snapshots.append(
            BrokerPositionSnapshot(
                symbol=_parse_str(getattr(position, "symbol", None)),
                qty=_position_qty_str(getattr(position, "qty", None)),
                side=_position_side_str(getattr(position, "side", None)),
            )
        )
    return {"ok": True, "positions": snapshots, "failure_reasons": ""}


def _positions_by_symbol(
    snapshots: list[BrokerPositionSnapshot],
) -> dict[str, BrokerPositionSnapshot]:
    out: dict[str, BrokerPositionSnapshot] = {}
    for snap in snapshots:
        if snap.symbol:
            out[snap.symbol] = snap
    return out


def _qty_matches(position_qty: str, expected: int | None) -> bool:
    if not position_qty:
        return False
    try:
        actual = float(position_qty)
    except ValueError:
        return False
    if not math.isfinite(actual) or actual == 0:
        return False
    if expected is None:
        return abs(actual) > 0
    return abs(abs(actual) - float(expected)) < 1e-9


def _leg_found(
    positions: dict[str, BrokerPositionSnapshot],
    *,
    symbol: str,
    expected_side: str,
    expected_qty: int | None,
) -> tuple[bool, str]:
    if not symbol:
        return False, ""
    snap = positions.get(symbol)
    if snap is None:
        return False, ""
    if snap.side != expected_side:
        return False, ""
    if not _qty_matches(snap.qty, expected_qty):
        return False, snap.qty
    return True, snap.qty


def classify_position_status(
    *,
    long_found: bool,
    short_found: bool,
    audit_error: bool,
) -> PositionStatus:
    if audit_error:
        return "POSITION_AUDIT_ERROR"
    if long_found and short_found:
        return "POSITION_CONFIRMED"
    if long_found or short_found:
        return "POSITION_PARTIAL"
    return "POSITION_NOT_FOUND"


def audit_one_filled_order(
    row: FilledOrderAuditInput,
    positions: dict[str, BrokerPositionSnapshot],
    *,
    fetch_ok: bool,
    fetch_failure: str,
) -> PaperPositionAudit:
    checked_at = _utc_now_iso()
    if not fetch_ok:
        return PaperPositionAudit(
            payload_id=row.payload_id,
            approval_id=row.approval_id,
            external_order_id=row.external_order_id,
            symbol=row.symbol,
            structure_type=row.structure_type,
            expected_long_leg_symbol=row.expected_long_leg_symbol,
            expected_short_leg_symbol=row.expected_short_leg_symbol,
            long_leg_position_found=False,
            short_leg_position_found=False,
            long_leg_qty="",
            short_leg_qty="",
            position_status="POSITION_AUDIT_ERROR",
            checked_at=checked_at,
            failure_reasons=fetch_failure,
            provenance=PROVENANCE_TAG,
        )

    if not row.expected_long_leg_symbol or not row.expected_short_leg_symbol:
        return PaperPositionAudit(
            payload_id=row.payload_id,
            approval_id=row.approval_id,
            external_order_id=row.external_order_id,
            symbol=row.symbol,
            structure_type=row.structure_type,
            expected_long_leg_symbol=row.expected_long_leg_symbol,
            expected_short_leg_symbol=row.expected_short_leg_symbol,
            long_leg_position_found=False,
            short_leg_position_found=False,
            long_leg_qty="",
            short_leg_qty="",
            position_status="POSITION_AUDIT_ERROR",
            checked_at=checked_at,
            failure_reasons="missing_expected_leg_symbols",
            provenance=PROVENANCE_TAG,
        )

    long_found, long_qty = _leg_found(
        positions,
        symbol=row.expected_long_leg_symbol,
        expected_side="long",
        expected_qty=row.expected_long_leg_qty,
    )
    short_found, short_qty = _leg_found(
        positions,
        symbol=row.expected_short_leg_symbol,
        expected_side="short",
        expected_qty=row.expected_short_leg_qty,
    )
    status = classify_position_status(
        long_found=long_found,
        short_found=short_found,
        audit_error=False,
    )
    return PaperPositionAudit(
        payload_id=row.payload_id,
        approval_id=row.approval_id,
        external_order_id=row.external_order_id,
        symbol=row.symbol,
        structure_type=row.structure_type,
        expected_long_leg_symbol=row.expected_long_leg_symbol,
        expected_short_leg_symbol=row.expected_short_leg_symbol,
        long_leg_position_found=long_found,
        short_leg_position_found=short_found,
        long_leg_qty=long_qty,
        short_leg_qty=short_qty,
        position_status=status,
        checked_at=checked_at,
        failure_reasons="",
        provenance=PROVENANCE_TAG,
    )


def run_paper_position_audit(
    rows: list[FilledOrderAuditInput],
    *,
    limit: int = 1,
    require_paper_endpoint: bool = True,
    get_positions_fn: PaperPositionsGetFn | None = None,
) -> tuple[list[PaperPositionAudit], str | None]:
    filled = filter_filled_order_audit_inputs(rows)
    if limit is not None and limit >= 0:
        filled = filled[:limit]

    if not filled:
        return [], None

    credentials = resolve_alpaca_paper_credentials(require_paper_endpoint=require_paper_endpoint)
    if credentials is None:
        return [], "paper_credentials_not_ready"

    fetch = get_positions_fn or get_alpaca_paper_positions
    raw = fetch(credentials)
    fetch_ok = bool(raw.get("ok"))
    fetch_failure = _parse_str(raw.get("failure_reasons"))
    snapshots = raw.get("positions")
    if not isinstance(snapshots, list):
        snapshots = []
    position_index = _positions_by_symbol(snapshots)

    audits = [
        audit_one_filled_order(
            row,
            position_index,
            fetch_ok=fetch_ok,
            fetch_failure=fetch_failure,
        )
        for row in filled
    ]
    return audits, None


def paper_position_audit_to_dataframe(audits: list[PaperPositionAudit]) -> pd.DataFrame:
    if not audits:
        return pd.DataFrame(columns=[f.name for f in fields(PaperPositionAudit)])
    return pd.DataFrame(
        [{f.name: getattr(a, f.name) for f in fields(PaperPositionAudit)} for a in audits]
    )


def summarize_paper_position_audit(
    all_inputs: list[FilledOrderAuditInput],
    audits: list[PaperPositionAudit],
) -> dict[str, object]:
    filled = filter_filled_order_audit_inputs(all_inputs)
    return {
        "filled_orders_found": len(filled),
        "position_checks_attempted": len(audits),
    }
