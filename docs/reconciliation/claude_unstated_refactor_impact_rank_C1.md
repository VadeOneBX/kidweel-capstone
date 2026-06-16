# Claude Unstated Refactor Impact Rank

Packet CLAUDE-PRIVACY-SUBAGENT-BT-C1 (Part 3). **Do not repost or accept the full refactor.** Impact-ranked review only.

## Scope reviewed

- `git status --short` (untracked / dirty items at audit time)
- Recent commit history (`git log --oneline -15` on current branch)
- Presence of `.claude/worktrees/` and untracked `alpaca-mcp-server/`
- No full directory repost; no `src/` edits in this packet

## Ranking method

Ordered impact classes:

1. Execution or transport impact  
2. Schema or gate impact  
3. Data ingestion impact  
4. Backtest evidence impact  
5. Docs/navigation impact  
6. Cosmetic impact  

## Highest impact changes

1. **Untracked `alpaca-mcp-server/` (~2.2M)** — External MCP server tree in repo root. Risk: operators confuse advisory workflows with transport tooling; potential credential/MCP config drift. **Not accepted** without an approved paper-transport packet. Manual review before any commit or wire-up.
2. **`.claude/worktrees/serene-payne-e47603/` (~1.7M duplicate tree)** — Full parallel copy of project under Claude worktrees. Risk: edits land in wrong tree; silent divergence from canonical `src/`. **Do not carry forward** as a second source of truth.
3. **Committed paper bridge / chain snapshot foundation** (recent history: `f6338db`, `084144b`, `f094eeb`) — Legitimate tracked features, but broad surface area if mixed with unstated local trees. Requires normal packet review when changing behavior — not part of unstated untracked refactor.

## Medium impact changes

1. **README / operating-loop doc commits** (`5eb1ea1`, `165ea33`) — Navigation and doctrine presentation; no execution code, but shapes how agents interpret authority.
2. **Untracked `examples/options-bull-call-spread.ipynb`** — Research notebook; backtest evidence impact if mistaken for production path. Keep out of transport path.
3. **`data/processed/*.csv` local artifacts** — Replay candidates and paper audit CSVs; ingestion/backtest context only (gitignored via `data/*`).

## Low impact changes

1. **Untracked `STYLE.md`** — Cosmetic / local style notes.
2. **`.DS_Store` under data/** — Noise; not architectural.

## Risk flags

- Duplicate worktree vs canonical `src/` → wrong-file edits  
- MCP server clone adjacent to paper-only repo → transport leakage in operator workflow  
- Mock / research notebooks presented without `missing_context` labels  

## Files requiring manual review

- `alpaca-mcp-server/` (entire tree — commit or delete explicitly)
- `.claude/worktrees/` (should not enter git)
- `examples/options-bull-call-spread.ipynb` (intent: research vs product)

## Recommended coming packet

Narrow **MCP transport boundary** packet: either document-ignore `alpaca-mcp-server/` with a root pointer to `docs/alpaca-paper-bridge.md`, or vendor it via approved submodule path — **one** explicit decision, no drive-by import.

Separate **worktree hygiene** note in operator docs (no code): delete stale `.claude/worktrees/*` after sessions.

## Do not carry forward

- Entire unstated duplicate worktree as implementation source  
- Whole `alpaca-mcp-server/` commit without transport packet  
- Any advisory artifact that labels synthetic PnL as live  

## Required final recommendation

**Do not repost or accept the full refactor. Convert only high-value findings into narrow packets.**
