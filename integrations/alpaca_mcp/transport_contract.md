# Transport contract (C10A)

Contract for **paper-intended** MCP request/response shapes **without** assuming a live network call. Real Alpaca/MCP behavior must conform to this contract when implemented.

**C11A (mock):** `mock_mcp_transport` already returns dicts that satisfy the raw shape below. **Future real paper MCP:** any broker or MCP tool response must be mapped into this **exact** five-key dict (`accepted`, `status`, `broker_mode`, `external_order_id`, `message`) before calling `normalize_mcp_response`—no extra keys, no omissions.

## Request shape (`MCPExecutionRequest`)

| Field | Meaning |
|--------|---------|
| `symbol`, `playbook`, `structure_type`, `expiry` | Typed handoff; strings must be non-empty after strip where applicable |
| `debit_or_credit`, `max_profit`, `max_loss` | Positive finite economics |
| `rr_actual`, `pmp` | Risk metrics; `pmp` strictly between 0 and 1 |
| `tp_rule`, `sl_rule`, `time_exit_rule` | Exit policy labels |
| `paper_only` | Must be `True` in this packet; no live-mode flag exists |

**Paper assertions:** `paper_only` is always `True` when built from an approved `ExecutionPayload` via `build_mcp_request`. `mcp_paper_gate` rejects any request with `paper_only` not `True`.

## Failure cases (gate)

Transport must **not** proceed when `mcp_paper_gate` returns `(False, reason)`. Reasons are explicit, machine-oriented strings (e.g. `paper_only_required`, `invalid_pmp_range`). **Fail-closed:** ambiguous or invalid requests are denied.

## Normalized response shape (`MCPExecutionResponse`)

| Field | Meaning |
|--------|---------|
| `accepted` | Whether the transport layer accepted the normalized outcome |
| `status` | Short status label from the transport |
| `broker_mode` | Normalized mode string; must be `"paper"` when `accepted` is `True` |
| `external_order_id` | Broker id if any; may be `None` |
| `message` | Human-readable message; must remain explicit when `accepted` is `False` |

**Raw dict rules:** `normalize_mcp_response` accepts **only** the keys `accepted`, `status`, `broker_mode`, `external_order_id`, `message` — no extras, no omissions. **Accepted** responses must have `broker_mode == "paper"`. Violations raise `ValueError` with a clear cause.

## Audit expectations

Downstream audit should record: payload identity (symbol, playbook), gate outcomes (`paper_execution_gate`, `mcp_paper_gate`), normalized response (`MCPExecutionResponse`), and explicit denial reasons. No silent coercion of broker errors into success.
