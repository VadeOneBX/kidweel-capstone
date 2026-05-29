# Alpaca MCP integration (scaffold)

## Purpose

This directory documents the **narrow paper-only** boundary between the Kidweel decision system and Alpaca’s transport surface (official MCP server and Trading API). The repo owns **what** may execute; MCP and broker APIs are **transport**, not judgment.

Alpaca provides **paper trading** as a simulated environment (paper accounts are distinct in Alpaca’s documentation). Options orders use the same Orders API family with options-specific rules described in Alpaca’s options documentation. Historical market data for equities and options is documented separately. The **official Alpaca MCP server** exposes a **broad** tool surface; this repo **intentionally consumes less** than the server offers (see `tool_surface.md`).

## Posture

- **Paper only** for this integration path. No live trading mode in this scaffold.
- **No autonomous loops**, no background daemons, no broker-driven decisions.
- **Repo authority chain** is unchanged: upstream modules produce typed contracts; execution emits an `ExecutionPayload`; MCP scaffolding translates and validates for transport only.

## MCP is transport

MCP tools carry **approved, typed payloads** toward paper execution. They do not screen candidates, alter playbooks, or re-derive regime, confidence, or gamma.

## Implementation status

| Packet | Role |
|--------|------|
| **C10A** | Narrow transport contract (`transport_contract.md`) and typed request/response models in `src/qops/execution/` |
| **C11A** | **Offline** mock bridge: `mcp_paper_gate` → `mock_mcp_transport` → `normalize_mcp_response` → audit (no network) |
| **Future** | Real **paper** Alpaca MCP client — explicit packet only; broker-shaped responses need a **pre-normalizer** into the five-key dict before normalization |

MCP remains **transport only**. The repo owns approval; transport carries approved payloads.

## Out of scope (until an explicit packet authorizes otherwise)

- Real broker submission, HTTP clients, SDK calls, or live MCP invocation
- Live trading mode, position management, fills polling, cancel/replace workflows
- Credential handling or environment probing

## Related docs

- `tool_surface.md` — allowed vs forbidden conceptual tool classes
- `transport_contract.md` — request/response expectations and audit expectations
