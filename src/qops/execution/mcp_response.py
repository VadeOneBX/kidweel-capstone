"""Normalize raw MCP-like transport dicts into stable repo-side responses."""

from __future__ import annotations

from qops.execution.mcp_models import MCPExecutionResponse

_REQUIRED_KEYS: frozenset[str] = frozenset(
    {
        "accepted",
        "status",
        "broker_mode",
        "external_order_id",
        "message",
    }
)


def normalize_mcp_response(raw: dict) -> MCPExecutionResponse:
    """
    Normalize a raw dict-like transport response into MCPExecutionResponse.

    Accepts only the narrow key set defined for this packet. Rejects missing keys,
    unknown keys, and type or contract violations.

    Raises:
        TypeError: If raw is not a dict.
        ValueError: If required fields are missing, invalid, or contract-violating.
    """
    if not isinstance(raw, dict):
        raise TypeError("raw response must be a dict")

    keys = set(raw.keys())
    if keys != _REQUIRED_KEYS:
        missing = sorted(_REQUIRED_KEYS - keys)
        extra = sorted(keys - _REQUIRED_KEYS)
        parts: list[str] = []
        if missing:
            parts.append(f"missing_keys={missing}")
        if extra:
            parts.append(f"unexpected_keys={extra}")
        raise ValueError("invalid_mcp_response_shape: " + "; ".join(parts))

    accepted = raw["accepted"]
    status = raw["status"]
    broker_mode = raw["broker_mode"]
    external_order_id = raw["external_order_id"]
    message = raw["message"]

    if not isinstance(accepted, bool):
        raise ValueError("accepted must be bool")
    if not isinstance(status, str) or not status.strip():
        raise ValueError("status must be a non-empty str")
    if not isinstance(broker_mode, str) or not broker_mode.strip():
        raise ValueError("broker_mode must be a non-empty str")
    if external_order_id is not None and not isinstance(external_order_id, str):
        raise ValueError("external_order_id must be str or None")
    if not isinstance(message, str):
        raise ValueError("message must be str")

    if accepted and broker_mode != "paper":
        raise ValueError("accepted responses require broker_mode == 'paper'")

    if not accepted and not message.strip():
        raise ValueError("rejected responses require an explicit non-empty message")

    return MCPExecutionResponse(
        accepted=accepted,
        status=status,
        broker_mode=broker_mode,
        external_order_id=external_order_id,
        message=message,
    )
