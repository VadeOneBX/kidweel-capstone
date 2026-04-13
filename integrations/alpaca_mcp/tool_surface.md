# MCP tool surface (repo-narrow)

The **official Alpaca MCP server** supports many actions (account, market data, orders, and more). This repository **deliberately** maps only a **subset** of that surface over time. Anything not listed as allowed for a future packet remains **forbidden** until explicitly authorized.

## Allowed later (conceptual classes only)

- **Account / context read** — read-only, for verifying paper context before transport (not implemented in C10A).
- **Paper order request transport** — submit an order **only** from an approved, gated execution request (not implemented in C10A).
- **Order status normalization** — map broker-shaped status to repo `MCPExecutionResponse` fields (not implemented in C10A).

## Forbidden now

- **Live orders** or any non-paper execution path
- **Cancel / replace** logic or multi-step order mutation
- **Position liquidation** or forced-exit automation
- **Portfolio mutation** beyond a single instructed paper order transport
- **Watchlists** and discretionary screening tools
- **Crypto** and instruments outside the repo’s current structure scope
- **Data analysis / research tools** that bypass repo logic and could substitute for the decision chain

## Rule

If a tool is not in the **Allowed later** list for the current packet, **do not wire it**. Broad MCP capability is a liability unless narrowed by these rules.
