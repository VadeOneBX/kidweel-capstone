"""Alpaca paper transport for PAPER_PAYLOAD_READY candidates (explicit submit only)."""

from __future__ import annotations

import math
import os
import shutil
import subprocess
from dataclasses import dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal, Protocol

import pandas as pd

from qops.execution.mcp_response import normalize_mcp_response
from qops.execution.paper_payload_candidate import PaperPayloadCandidate, PayloadStatus
from qops.schemas.playbook import AllowedPlaybook

PROVENANCE_TAG = "mcp_c12a_alpaca_paper_bridge"
CANONICAL_PAPER_BASE_URL = "https://paper-api.alpaca.markets"
PROFILE_CLI_SUBMIT_NOT_IMPLEMENTED = "PROFILE_CLI_SUBMIT_NOT_IMPLEMENTED"

AuthMode = Literal["env_triplet", "profile_cli"]
ConfigSource = Literal["env", "default", "unknown"]
ProfileCliCredentialStatus = Literal[
    "READY_PROFILE_AUTH_PAPER_DEFAULT",
    "LIVE_ENV_FORBIDDEN",
    "PROFILE_UNREADABLE",
    "ACCOUNT_CHECK_FAILED",
    "CLI_NOT_FOUND",
    "AUTH_FAILED",
    "UNKNOWN",
]

_FORBIDDEN_ALPACA_CLI_FLAGS = frozenset({"--secret", "--live"})

TransportStatus = Literal[
    "PAPER_DRY_RUN_READY",
    "PAPER_SUBMITTED",
    "PAPER_REJECTED",
    "PAPER_TRANSPORT_ERROR",
    "PAPER_SKIPPED",
]

_CREDIT_STRUCTURES = frozenset(
    {
        AllowedPlaybook.BULL_PUT_CREDIT_SPREAD.value,
        AllowedPlaybook.BEAR_CALL_CREDIT_SPREAD.value,
    }
)

_PAPER_CREDENTIAL_PAIRS: tuple[tuple[str, str, str, str], ...] = (
    ("ALPACA_PAPER_API_KEY", "ALPACA_PAPER_SECRET_KEY", "ALPACA_PAPER_BASE_URL", "ALPACA_PAPER_*"),
    ("APCA_API_KEY_ID", "APCA_API_SECRET_KEY", "APCA_API_BASE_URL", "APCA_*"),
)

_PREFERRED_PAPER_ENV_KEYS: tuple[str, ...] = (
    "ALPACA_PAPER_API_KEY",
    "ALPACA_PAPER_SECRET_KEY",
    "ALPACA_PAPER_BASE_URL",
)


def repo_root_env_path() -> Path:
    """Path to repo-root `.env` (never read or printed by callers)."""
    return Path(__file__).resolve().parents[3] / ".env"


def load_local_env(*, env_path: Path | None = None) -> bool:
    """
    Load local `.env` when python-dotenv is available.

    Does not override already-exported environment variables. Never raises on
    permission errors; never logs values.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return False
    path = env_path if env_path is not None else repo_root_env_path()
    if not path.is_file():
        return False
    try:
        load_dotenv(path, override=False)
    except PermissionError:
        return False
    return True


def _triplet_missing_keys(key_name: str, secret_name: str, url_name: str) -> tuple[str, ...]:
    missing: list[str] = []
    if not _env_nonempty(key_name):
        missing.append(key_name)
    if not _env_nonempty(secret_name):
        missing.append(secret_name)
    if not _env_nonempty(url_name):
        missing.append(url_name)
    return tuple(missing)


def _env_nonempty(name: str) -> str | None:
    raw = os.environ.get(name)
    if raw is None:
        return None
    value = str(raw).strip()
    return value if value else None


def normalize_paper_base_url(url: str) -> str:
    return url.strip().rstrip("/")


def validate_paper_endpoint(
    base_url: str | None,
    *,
    require_paper_endpoint: bool = True,
) -> tuple[bool, str]:
    if not base_url or not str(base_url).strip():
        return False, "missing_paper_base_url"
    normalized = normalize_paper_base_url(base_url)
    if normalized == "https://api.alpaca.markets":
        return False, "live_endpoint_forbidden"
    if require_paper_endpoint and normalized != CANONICAL_PAPER_BASE_URL:
        return False, "paper_endpoint_must_be_canonical"
    if normalized != CANONICAL_PAPER_BASE_URL:
        return False, "non_paper_endpoint_forbidden"
    return True, "paper_endpoint_ok"


@dataclass(frozen=True, slots=True)
class AlpacaProfileCliCredentialCheck:
    credential_status: ProfileCliCredentialStatus
    auth_mode: AuthMode
    detail: str | None
    cli_argv: tuple[str, ...]
    account_check_argv: tuple[str, ...]
    config_dir_source: ConfigSource
    profile_source: ConfigSource
    live_env_status: str


@dataclass(frozen=True, slots=True)
class AlpacaPaperCredentialCheck:
    credential_status: Literal["READY", "MISSING"]
    env_pair_label: str | None
    base_url: str | None
    endpoint_ok: bool
    endpoint_detail: str
    missing_keys: tuple[str, ...]
    detail: str | None


@dataclass(frozen=True, slots=True)
class AlpacaPaperCredentials:
    api_key: str
    secret_key: str
    base_url: str
    env_pair_label: str


@dataclass(frozen=True, slots=True)
class PaperTransportResult:
    payload_id: str
    approval_id: str
    symbol: str
    structure_type: str
    transport_status: TransportStatus
    dry_run: bool
    broker_mode: str
    external_order_id: str | None
    accepted: bool
    status: str
    message: str
    submitted_at: str | None
    failure_reasons: str
    provenance: str


class PaperMlegSubmitFn(Protocol):
    def __call__(
        self,
        credentials: AlpacaPaperCredentials,
        payload: PaperPayloadCandidate,
    ) -> dict: ...


def build_profile_cli_env_check_argv(*, executable: str = "alpaca") -> list[str]:
    """Read-only Alpaca CLI profile check (automation: always includes --quiet)."""
    return [executable, "profile", "show", "--quiet"]


def build_profile_cli_account_check_argv(*, executable: str = "alpaca") -> list[str]:
    """Read-only Alpaca CLI account check (automation: always includes --quiet)."""
    return [executable, "account", "get", "--quiet"]


def assert_no_forbidden_alpaca_cli_flags(argv: list[str]) -> None:
    for token in argv:
        if token in _FORBIDDEN_ALPACA_CLI_FLAGS or token.startswith("--secret="):
            raise ValueError(f"forbidden_alpaca_cli_flag:{token}")


def _live_trade_env_forbidden() -> bool:
    raw = os.environ.get("ALPACA_LIVE_TRADE")
    if raw is None:
        return False
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _live_env_status() -> str:
    if os.environ.get("ALPACA_LIVE_TRADE") is None:
        return "missing"
    if _live_trade_env_forbidden():
        return "true"
    return "false"


def _config_dir_source() -> ConfigSource:
    if _env_nonempty("ALPACA_CONFIG_DIR"):
        return "env"
    return "default"


def _profile_name_source() -> ConfigSource:
    if _env_nonempty("ALPACA_PROFILE"):
        return "env"
    return "default"


def _profile_cli_check_result(
    *,
    credential_status: ProfileCliCredentialStatus,
    detail: str | None,
    cli_argv: tuple[str, ...],
    account_check_argv: tuple[str, ...],
    config_dir_source: ConfigSource,
    profile_source: ConfigSource,
    live_env_status: str,
) -> AlpacaProfileCliCredentialCheck:
    return AlpacaProfileCliCredentialCheck(
        credential_status=credential_status,
        auth_mode="profile_cli",
        detail=detail,
        cli_argv=cli_argv,
        account_check_argv=account_check_argv,
        config_dir_source=config_dir_source,
        profile_source=profile_source,
        live_env_status=live_env_status,
    )


def check_alpaca_profile_cli_credentials(
    *,
    executable: str = "alpaca",
    run: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> AlpacaProfileCliCredentialCheck:
    """Read-only Alpaca CLI profile + account readiness (no secrets printed, no submit)."""
    profile_argv = build_profile_cli_env_check_argv(executable=executable)
    account_argv = build_profile_cli_account_check_argv(executable=executable)
    assert_no_forbidden_alpaca_cli_flags(profile_argv)
    assert_no_forbidden_alpaca_cli_flags(account_argv)
    cli_tuple = tuple(profile_argv)
    account_tuple = tuple(account_argv)
    config_src = _config_dir_source()
    profile_src = _profile_name_source()
    live_status = _live_env_status()

    def result(
        credential_status: ProfileCliCredentialStatus,
        detail: str | None,
    ) -> AlpacaProfileCliCredentialCheck:
        return _profile_cli_check_result(
            credential_status=credential_status,
            detail=detail,
            cli_argv=cli_tuple,
            account_check_argv=account_tuple,
            config_dir_source=config_src,
            profile_source=profile_src,
            live_env_status=live_status,
        )

    if _live_trade_env_forbidden():
        return result("LIVE_ENV_FORBIDDEN", "ALPACA_LIVE_TRADE_true")

    if shutil.which(executable) is None:
        return result("CLI_NOT_FOUND", "alpaca_cli_not_on_path")

    runner = run if run is not None else subprocess.run
    cli_env = os.environ.copy()

    def run_cmd(argv: list[str]) -> subprocess.CompletedProcess[str]:
        return runner(
            argv,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env=cli_env,
        )

    try:
        profile_proc = run_cmd(profile_argv)
    except FileNotFoundError:
        return result("CLI_NOT_FOUND", "alpaca_cli_not_found")
    except subprocess.TimeoutExpired:
        return result("UNKNOWN", "profile_cli_timeout")

    if profile_proc.returncode == 2:
        return result("AUTH_FAILED", "alpaca_cli_profile_exit_code_2")
    if profile_proc.returncode != 0:
        return result("PROFILE_UNREADABLE", f"profile_show_exit_code_{profile_proc.returncode}")

    try:
        account_proc = run_cmd(account_argv)
    except subprocess.TimeoutExpired:
        return result("UNKNOWN", "account_check_timeout")

    if account_proc.returncode == 2:
        return result("AUTH_FAILED", "alpaca_cli_account_exit_code_2")
    if account_proc.returncode != 0:
        return result("ACCOUNT_CHECK_FAILED", f"account_get_exit_code_{account_proc.returncode}")

    return result("READY_PROFILE_AUTH_PAPER_DEFAULT", "profile_and_account_ok")


def profile_cli_submit_blocked(auth_mode: AuthMode, *, submit_paper: bool) -> str | None:
    if submit_paper and auth_mode == "profile_cli":
        return PROFILE_CLI_SUBMIT_NOT_IMPLEMENTED
    return None


def check_alpaca_paper_credentials(
    *,
    require_paper_endpoint: bool = True,
) -> AlpacaPaperCredentialCheck:
    for key_name, secret_name, url_name, label in _PAPER_CREDENTIAL_PAIRS:
        key = _env_nonempty(key_name)
        secret = _env_nonempty(secret_name)
        base_url = _env_nonempty(url_name)
        if key and secret and base_url:
            endpoint_ok, endpoint_detail = validate_paper_endpoint(
                base_url,
                require_paper_endpoint=require_paper_endpoint,
            )
            if not endpoint_ok:
                return AlpacaPaperCredentialCheck(
                    credential_status="MISSING",
                    env_pair_label=label,
                    base_url=base_url,
                    endpoint_ok=False,
                    endpoint_detail=endpoint_detail,
                    missing_keys=(),
                    detail=endpoint_detail,
                )
            return AlpacaPaperCredentialCheck(
                credential_status="READY",
                env_pair_label=label,
                base_url=normalize_paper_base_url(base_url),
                endpoint_ok=True,
                endpoint_detail=endpoint_detail,
                missing_keys=(),
                detail=None,
            )
        if key or secret or base_url:
            endpoint_ok, endpoint_detail = validate_paper_endpoint(
                base_url,
                require_paper_endpoint=require_paper_endpoint,
            )
            missing_keys = _triplet_missing_keys(key_name, secret_name, url_name)
            return AlpacaPaperCredentialCheck(
                credential_status="MISSING",
                env_pair_label=label,
                base_url=base_url,
                endpoint_ok=endpoint_ok,
                endpoint_detail=endpoint_detail,
                missing_keys=missing_keys,
                detail="incomplete_credential_triplet",
            )
    return AlpacaPaperCredentialCheck(
        credential_status="MISSING",
        env_pair_label=None,
        base_url=None,
        endpoint_ok=False,
        endpoint_detail="missing_paper_base_url",
        missing_keys=_PREFERRED_PAPER_ENV_KEYS,
        detail="no_paper_credential_triplet",
    )


def resolve_alpaca_paper_credentials(
    *,
    require_paper_endpoint: bool = True,
) -> AlpacaPaperCredentials | None:
    load_local_env()
    check = check_alpaca_paper_credentials(require_paper_endpoint=require_paper_endpoint)
    if check.credential_status != "READY" or not check.endpoint_ok:
        return None
    for key_name, secret_name, url_name, label in _PAPER_CREDENTIAL_PAIRS:
        key = _env_nonempty(key_name)
        secret = _env_nonempty(secret_name)
        base_url = _env_nonempty(url_name)
        if key and secret and base_url:
            return AlpacaPaperCredentials(
                api_key=key,
                secret_key=secret,
                base_url=normalize_paper_base_url(base_url),
                env_pair_label=label,
            )
    return None


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


def load_paper_payload_rows(path: str | Path) -> list[PaperPayloadCandidate]:
    p = Path(path)
    if not p.is_file():
        return []
    df = pd.read_csv(p)
    out: list[PaperPayloadCandidate] = []
    for _, series in df.iterrows():
        status_raw = _parse_str(series.get("payload_status"))
        if status_raw in {"PAPER_PAYLOAD_READY", "REJECTED", "INCOMPLETE"}:
            status_literal: PayloadStatus = status_raw  # type: ignore[assignment]
        else:
            status_literal = "REJECTED"
        out.append(
            PaperPayloadCandidate(
                payload_id=_parse_str(series.get("payload_id")),
                approval_id=_parse_str(series.get("approval_id")),
                symbol=_parse_str(series.get("symbol")),
                trade_date=_parse_str(series.get("trade_date")),
                structure_type=_parse_str(series.get("structure_type")),
                order_class=_parse_str(series.get("order_class"), "mleg"),
                order_type=_parse_str(series.get("order_type"), "limit"),
                time_in_force=_parse_str(series.get("time_in_force"), "day"),
                qty=_parse_int(series.get("qty")),
                limit_price=_parse_float(series.get("limit_price")),
                max_loss=_parse_float(series.get("max_loss")),
                max_profit=_parse_float(series.get("max_profit")),
                reward_risk=_parse_float(series.get("reward_risk")),
                pmp=_parse_float(series.get("pmp")),
                pmp_source=_parse_str(series.get("pmp_source"), "missing"),
                pmp_confidence=_parse_str(series.get("pmp_confidence"), "MISSING"),
                expected_value=_parse_float(series.get("expected_value")),
                long_leg_symbol=_parse_str(series.get("long_leg_symbol")),
                short_leg_symbol=_parse_str(series.get("short_leg_symbol")),
                long_leg_side=_parse_str(series.get("long_leg_side")),
                short_leg_side=_parse_str(series.get("short_leg_side")),
                long_leg_qty=_parse_int(series.get("long_leg_qty")),
                short_leg_qty=_parse_int(series.get("short_leg_qty")),
                expiration=_parse_str(series.get("expiration")),
                approval_status=_parse_str(series.get("approval_status")),
                payload_status=status_literal,  # type: ignore[arg-type]
                payload_reason=_parse_str(series.get("payload_reason")),
                failure_reasons=_parse_str(series.get("failure_reasons")),
                provenance=_parse_str(series.get("provenance")),
            )
        )
    return out


def filter_ready_payloads(rows: list[PaperPayloadCandidate]) -> list[PaperPayloadCandidate]:
    return [r for r in rows if r.payload_status == "PAPER_PAYLOAD_READY"]


def effective_transport_limit(*, submit_paper: bool, limit: int | None) -> int:
    if limit is not None and limit > 0:
        return limit
    return 1 if submit_paper else 1


def _alpaca_parent_side(structure_type: str):
    from alpaca.trading.enums import OrderSide

    if structure_type in _CREDIT_STRUCTURES:
        return OrderSide.SELL
    return OrderSide.BUY


def deterministic_client_order_id(payload: PaperPayloadCandidate) -> str:
    """Stable Alpaca client order id for idempotent automation (derived from payload_id)."""
    if not payload.payload_id:
        raise ValueError("payload_id required for client_order_id")
    # Alpaca client_order_id length limit is 48 characters.
    return f"qops-paper-{payload.payload_id}"[:48]


def _alpaca_net_limit_price(structure_type: str, limit_price: float) -> float:
    if structure_type in _CREDIT_STRUCTURES:
        return -abs(limit_price)
    return abs(limit_price)


def _open_position_intent_for_leg_side(side: object) -> object:
    from alpaca.trading.enums import OrderSide, PositionIntent

    if side == OrderSide.BUY:
        return PositionIntent.BUY_TO_OPEN
    return PositionIntent.SELL_TO_OPEN


def build_alpaca_mleg_order_request(payload: PaperPayloadCandidate):
    """Map repo payload fields to alpaca-py multileg limit order (adapter only)."""
    from alpaca.trading.enums import OrderClass, OrderSide, OrderType, TimeInForce
    from alpaca.trading.requests import LimitOrderRequest, OptionLegRequest

    if payload.qty is None or payload.qty <= 0:
        raise ValueError("payload.qty must be positive")
    if payload.limit_price is None or payload.limit_price <= 0:
        raise ValueError("payload.limit_price must be positive")

    long_side = OrderSide.BUY if payload.long_leg_side == "buy" else OrderSide.SELL
    short_side = OrderSide.BUY if payload.short_leg_side == "buy" else OrderSide.SELL
    if payload.long_leg_qty is None or payload.short_leg_qty is None:
        raise ValueError("payload leg qty required")

    legs = [
        OptionLegRequest(
            symbol=payload.long_leg_symbol,
            ratio_qty=float(payload.long_leg_qty),
            side=long_side,
            position_intent=_open_position_intent_for_leg_side(long_side),
        ),
        OptionLegRequest(
            symbol=payload.short_leg_symbol,
            ratio_qty=float(payload.short_leg_qty),
            side=short_side,
            position_intent=_open_position_intent_for_leg_side(short_side),
        ),
    ]
    return LimitOrderRequest(
        symbol=None,
        qty=float(payload.qty),
        side=_alpaca_parent_side(payload.structure_type),
        type=OrderType.LIMIT,
        time_in_force=TimeInForce.DAY,
        order_class=OrderClass.MLEG,
        legs=legs,
        limit_price=_alpaca_net_limit_price(payload.structure_type, payload.limit_price),
        client_order_id=deterministic_client_order_id(payload),
    )


def sanitize_alpaca_mleg_order_request(request: object) -> dict[str, object]:
    """JSON-safe broker request preview (no secrets)."""
    if not hasattr(request, "model_dump"):
        raise TypeError("expected pydantic order request")
    raw = request.model_dump(mode="json")
    return {key: value for key, value in raw.items() if value is not None}


def alpaca_order_to_transport_raw(order: object, *, message_prefix: str = "order_submitted") -> dict:
    order_id = getattr(order, "id", None)
    status = getattr(order, "status", None)
    status_str = str(status.value if hasattr(status, "value") else status)
    external = str(order_id) if order_id is not None else None
    return {
        "accepted": True,
        "status": status_str,
        "broker_mode": "paper",
        "external_order_id": external,
        "message": f"{message_prefix}:{status_str}",
    }


def transport_error_raw(message: str) -> dict:
    return {
        "accepted": False,
        "status": "transport_error",
        "broker_mode": "paper",
        "external_order_id": None,
        "message": message,
    }


def submit_alpaca_paper_mleg_order(
    credentials: AlpacaPaperCredentials,
    payload: PaperPayloadCandidate,
) -> dict:
    """Submit one multileg order to Alpaca paper (network I/O)."""
    endpoint_ok, detail = validate_paper_endpoint(credentials.base_url)
    if not endpoint_ok:
        return transport_error_raw(detail)

    from alpaca.trading.client import TradingClient

    request = build_alpaca_mleg_order_request(payload)
    client = TradingClient(
        api_key=credentials.api_key,
        secret_key=credentials.secret_key,
        paper=True,
        url_override=credentials.base_url,
    )
    try:
        order = client.submit_order(order_data=request)
    except Exception as exc:
        return transport_error_raw(f"alpaca_submit_error:{type(exc).__name__}:{exc}")
    return alpaca_order_to_transport_raw(order)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dry_run_result(payload: PaperPayloadCandidate) -> PaperTransportResult:
    return PaperTransportResult(
        payload_id=payload.payload_id,
        approval_id=payload.approval_id,
        symbol=payload.symbol,
        structure_type=payload.structure_type,
        transport_status="PAPER_DRY_RUN_READY",
        dry_run=True,
        broker_mode="paper",
        external_order_id=None,
        accepted=False,
        status="dry_run",
        message="dry_run_no_broker_call",
        submitted_at=None,
        failure_reasons="",
        provenance=PROVENANCE_TAG,
    )


def run_paper_payload_transport(
    rows: list[PaperPayloadCandidate],
    *,
    submit_paper: bool = False,
    limit: int | None = None,
    require_paper_endpoint: bool = True,
    submit_fn: PaperMlegSubmitFn | None = None,
) -> tuple[list[PaperTransportResult], str | None]:
    """
    Transport ready payloads (dry-run default). Returns (results, fatal_error).

    fatal_error is set when submit_paper is True but credentials/endpoint fail closed.
    """
    transport_limit = effective_transport_limit(submit_paper=submit_paper, limit=limit)
    ready = filter_ready_payloads(rows)[:transport_limit]
    results: list[PaperTransportResult] = []

    if not submit_paper:
        results.extend(_dry_run_result(p) for p in ready)
        return results, None

    credentials = resolve_alpaca_paper_credentials(require_paper_endpoint=require_paper_endpoint)
    if credentials is None:
        check = check_alpaca_paper_credentials(require_paper_endpoint=require_paper_endpoint)
        reason = check.detail or check.endpoint_detail or "paper_credentials_not_ready"
        return results, reason

    submit_callable = submit_fn or submit_alpaca_paper_mleg_order

    for payload in ready:
        submitted_at = _utc_now_iso()
        raw = submit_callable(credentials, payload)
        try:
            normalized = normalize_mcp_response(raw)
        except ValueError as exc:
            results.append(
                PaperTransportResult(
                    payload_id=payload.payload_id,
                    approval_id=payload.approval_id,
                    symbol=payload.symbol,
                    structure_type=payload.structure_type,
                    transport_status="PAPER_TRANSPORT_ERROR",
                    dry_run=False,
                    broker_mode="paper",
                    external_order_id=None,
                    accepted=False,
                    status="normalize_error",
                    message=str(exc),
                    submitted_at=submitted_at,
                    failure_reasons="normalize_mcp_response_failed",
                    provenance=PROVENANCE_TAG,
                )
            )
            continue

        if normalized.accepted:
            transport_status: TransportStatus = "PAPER_SUBMITTED"
        else:
            transport_status = "PAPER_REJECTED"

        results.append(
            PaperTransportResult(
                payload_id=payload.payload_id,
                approval_id=payload.approval_id,
                symbol=payload.symbol,
                structure_type=payload.structure_type,
                transport_status=transport_status,
                dry_run=False,
                broker_mode=normalized.broker_mode,
                external_order_id=normalized.external_order_id,
                accepted=normalized.accepted,
                status=normalized.status,
                message=normalized.message,
                submitted_at=submitted_at,
                failure_reasons="" if normalized.accepted else normalized.message,
                provenance=PROVENANCE_TAG,
            )
        )

    return results, None


def paper_transport_to_dataframe(results: list[PaperTransportResult]) -> pd.DataFrame:
    if not results:
        return pd.DataFrame(columns=[f.name for f in fields(PaperTransportResult)])
    return pd.DataFrame([{f.name: getattr(r, f.name) for f in fields(PaperTransportResult)} for r in results])


def summarize_paper_transport(
    input_rows: list[PaperPayloadCandidate],
    results: list[PaperTransportResult],
) -> dict[str, object]:
    ready_count = len(filter_ready_payloads(input_rows))
    dry_ready = sum(1 for r in results if r.transport_status == "PAPER_DRY_RUN_READY")
    submitted = sum(1 for r in results if r.transport_status == "PAPER_SUBMITTED")
    return {
        "input_payload_candidates": len(input_rows),
        "paper_payload_ready_count": ready_count,
        "dry_run_ready_count": dry_ready,
        "paper_submitted_count": submitted,
        "transport_result_count": len(results),
    }
