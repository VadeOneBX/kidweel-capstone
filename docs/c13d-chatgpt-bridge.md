# C13D — ChatGPT enrichment bridge

## Prerequisite context for C13D

- Alpaca MCP Server v2 is the source of truth for MCP behavior.
- Do not assume v1 tool names, parameters, or config behavior.
- Clear Cursor MCP tool cache by restarting Cursor and using a fresh session.
- Restrict tools initially with: `ALPACA_TOOLSETS=assets,options-data`
- Treat SpotGamma processed csv/parquet as the candidate surface only.
- Use Alpaca options examples as the canonical source for structure semantics.
- Keep ChatGPT as the bounded synthesis layer, not a gate or executor.
- Do not build execution logic in C13D.
- Do not bypass deterministic repo logic.
- Do not add live trading support.

This aligns with the MCP v2 and Alpaca structure sources already mapped.

---

## Purpose

C13D establishes a ChatGPT-native enrichment bridge.

- **SpotGamma** provides the candidate surface.
- **Cursor** enforces deterministic gates.
- **Alpaca MCP** provides delayed chain context after OG gates pass.
- **ChatGPT** synthesizes vendor surface, market backdrop, and chain structure for user determination.

ChatGPT does not approve trades. ChatGPT does not size positions. ChatGPT does not execute orders.

The bridge reads processed SpotGamma CSVs, validates columns, builds compact candidate records with derived flags, optionally attaches SPY market context from the SPY market context store, reserves a stable `chain_context` stub for later MCP enrichment, and exports JSON for downstream use. It performs no MCP calls, no execution, and no approval.
