# C13C — Live dynamics (research layer)

This packet adds **research-only** context around SpotGamma candidates: SPY market backdrop, delayed options-chain summaries from locally persisted MCP-fed snapshots, and lightweight ML hooks. It does **not** change execution, risk, or approval authority.

## Delayed chain

Delayed chain handling is **research enrichment only**. Summaries are derived from **local chain snapshots** (for example, data previously obtained through Alpaca MCP delayed chain feeds). They inform narrative and feature rows; they are **not** a source of trade approval or sizing.

## ChatGPT

ChatGPT remains a **bounded context synthesis layer** and a **pre-execution reliability gate**: it helps the user interpret structure and constraints; it does **not** grant approval, position sizing, or execution authority.

## Authority boundaries

- **No approval authority** — OG gates and human review remain upstream of any action.
- **No sizing authority** — this layer does not compute or recommend size.
- **No execution authority** — no broker-side order placement is introduced here.

## SPY historical context

The SPY-only historical context store is **market backdrop** (regime-style labels vs vol trigger, walls as provided in the ingest CSV). It is **not** a substitute for single-name memory: single-name behavior must still be read from SpotGamma and chain context for that symbol.

## ML

ML components are **assistive and offline** by design: they prepare frames and simple models for exploration; they are **non-authoritative** and must not override deterministic gates or human judgment.
