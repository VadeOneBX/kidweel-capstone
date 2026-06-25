# reverse-risk-premium — post-ORB idea skill (AGENT-SKILLS-C2)

**Tier 3 advisory only.** Tools suggest; rules approve. No submit, size, route, or live endpoint.

## When

After opening range closes (post-ORB). Emit **exactly three** typed ideas per cycle.

## Idea contract

Same required fields as [squeeze-candidates.md](./squeeze-candidates.md).

Write artifact: `data/runs/<YYYY-MM-DD>/<run_id>_reverse-risk-premium_ideas.json`

`idea_source` at file level: `reverse-vrp`

## Three ideas (fixed order)

### 1 — Cheap vol signal

**Data:** IV Rank low, GARCH Rank, Options Implied Move.

**Output:** Whether IV is cheap vs. realized; debit expression **candidate flag** only.

### 2 — Catalyst proximity

**Catalyst field** in context row / coordinator events memo (cite path in `source`).

**Required:** event date and type in `data_basis`.

**Output:** Whether a near-term event could reprice IV.

### 3 — Implied move vs. spread cost

**Data:** Options Implied Move vs. spread debit (chain snapshot + SpotGamma CSV).

**Output:** Ratio check only (`implied_move_to_debit_ratio` in `data_basis`); not a trade recommendation.

## Redlines

- No idea without `source`.
- Ratio check #3 is advisory math only; no new broker endpoint.
- Ideas feed [claude-advisor-distillation.md](./claude-advisor-distillation.md) only.
