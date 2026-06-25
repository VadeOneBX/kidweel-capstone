# volatility-risk-premium — post-ORB idea skill (AGENT-SKILLS-C2)

**Tier 3 advisory only.** Tools suggest; rules approve. No submit, size, route, or live endpoint.

## When

After opening range closes (post-ORB). Emit **exactly three** typed ideas per cycle.

## Idea contract

Same required fields as [squeeze-candidates.md](./squeeze-candidates.md).

Write artifact: `data/runs/<YYYY-MM-DD>/<run_id>_volatility-risk-premium_ideas.json`

`idea_source` at file level: `vrp`

## Three ideas (fixed order)

### 1 — Premium richness read

**Data:** 1M IV − 1M RV (VRP), IV Rank.

**Output:** Whether IV is elevated vs. realized; `PROPOSE` credit only when VRP positive **and** rank elevated (advisory typing—not approval).

### 2 — Skew direction read

**Data:** NE Skew field, call vs. put skew comparison.

**Output:** Bullish / bearish / neutral skew signal; flag if call IV moves toward put IV.

### 3 — Wall-convergence check

**Data:** Call Wall distance, VRP direction.

**Output:** Whether call wall and VRP align for a directional expression.

## Redlines

- No idea without `source`.
- Credit `PROPOSE` typing does not bypass spread math, PMP, or paper gates.
- Ideas feed [claude-advisor-distillation.md](./claude-advisor-distillation.md) only.
