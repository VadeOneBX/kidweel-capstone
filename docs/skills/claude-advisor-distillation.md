# claude-advisor — idea distillation (AGENT-SKILLS-C2)

Deterministic distillation runs in-repo (`qops.advisory.idea_distillation`) and is summarized in `data/advisory/*_claude_brief.md`. The **claude-advisor** skill interprets flags; it does **not** approve, size, or route.

## Inputs

Nine ideas total: three per Tier 3 agent:

| Agent | Artifact suffix | `idea_source` |
|-------|-----------------|---------------|
| squeeze-candidates | `_squeeze-candidates_ideas.json` | `squeeze` |
| volatility-risk-premium | `_volatility-risk-premium_ideas.json` | `vrp` |
| reverse-risk-premium | `_reverse-risk-premium_ideas.json` | `reverse-vrp` |

**Stop:** Any idea missing `source` or `data_basis` → distillation blocked; coordinator notified; do not emit policy votes.

## Distillation steps

1. **Deduplicate** aligned ideas (same symbol + same directional thesis in `data_basis`) → consolidate; record `agreement_count`.
2. **Regime alignment** from manifest **context** CSV `regime_label` (do not re-derive): contradicting ideas → `regime_alignment: CONTRADICTS`.
3. **EV filter** — debit spread fields in `data_basis` (`structure_type`, `spread_width`, `net_debit`, `reference_strike`, `probability_of_profit`) evaluated via `qops.strategy.spread_math`. No advance without positive EV for that width.
4. **Rank** survivors by `dealer_tier` on manifest **expressions** artifact when present, else `confidence` on the context row for that symbol (artifact-sourced only).
5. **Policy vote** per surviving consolidated idea (ranked).

## Policy vote shape

```yaml
symbol:
idea_source:          # squeeze | vrp | reverse-vrp
idea_type:            # original agent idea_type
data_basis:
regime_alignment:     # ALIGNED | CONTRADICTS | NEUTRAL
ev_check:             # POSITIVE | NEGATIVE | MISSING_DATA
dealer_tier:          # A | B | C | D | E | NOT_SCORED
vote:                 # PROPOSE | WATCH | PASS
vote_reason:
rec_structure:        # only if vote = PROPOSE and ev_check = POSITIVE
agreement_count:      # optional after dedup
```

**Rules**

- `ev_check` negative or `MISSING_DATA` → `vote: PASS` with `vote_reason` (no exceptions).
- No `PROPOSE` with negative EV.
- All three ideas from one agent → all `PASS` after distillation → flag `AGENT_SIGNAL_WEAK:<agent_id>` for coordinator (valid output, not an error).

## Skill + agent boundary

- Tier 3 skills produce idea JSON only.
- claude-advisor skill may reason over distilled votes and supplied context; **no gate override**.
- Paper transport unchanged; no live endpoint.

## Reference

- [docs/claude-advisor-context.md](../claude-advisor-context.md)
- [docs/evidence_artifacts_guide.md](../evidence_artifacts_guide.md) (morning artifact chain)
- Tier 3 skills in this directory

## Artifact chain (post-ORB — not blueprint replay)

Read **run manifest** and linked artifacts only unless the packet scopes backtest:

| Need | Path |
|------|------|
| Run index | `data/runs/<run_date>/<run_id>_orb_manifest.json` |
| Tier 3 ideas | `data/runs/<run_date>/<run_id>_<agent>_ideas.json` |
| Distilled votes | `data/advisory/<run_id>_claude_brief.md` (policy `vote:` blocks) |
| Context / regime | manifest `context_artifact` |
| Dealer tier / quotes | manifest `expressions_artifact` |

**Do not** default to `examples/alpaca_blueprint_*.py`, `qops.backtest.alpaca_blueprint_adapter`, or C4A replay CSVs for morning advisory—those are historical replay planning, not ORB idea distillation.
