# squeeze-candidates — post-ORB idea skill (AGENT-SKILLS-C2)

**Tier 3 advisory only.** Tools suggest; rules approve. No submit, size, route, or live endpoint.

## When

After opening range closes (post-ORB). Emit **exactly three** typed ideas per cycle.

## Idea contract

Each idea **must** include:

| Field | Required |
|-------|----------|
| `idea_type` | `PROPOSE`, `WATCH`, or `PASS` |
| `symbol` | Underlying |
| `source` | Data lineage (file path, artifact id, or panel name) |
| `data_basis` | Object with fields used for the read |
| `reason` | One-line rationale |

Write artifact: `data/runs/<YYYY-MM-DD>/<run_id>_squeeze-candidates_ideas.json`

`idea_source` at file level: `squeeze`

## Three ideas (fixed order)

### 1 — Wall proximity setup

**Data:** Call Wall / Put Wall distance %, Options Impact from manifest **`context_artifact`** (SpotGamma-normalized rows). Optional coordinator memo: cite path in `source`.

**Output fields:** symbol, wall side, distance %, directional bias, `idea_type`.

### 2 — Gamma concentration signal

**Data:** Gamma field, price vs. wall.

**Output:** Whether gamma concentrates above or below current price; caution flag if ambiguous.

### 3 — ORB breach check

**Data:** ORB high/low vs. current price; 10-day SPX trend if symbol is SPY.

**Output:** Whether price cleared ORB range; directional confirmation or contradiction.

## Redlines

- No idea without `source`.
- `PASS` is valid; not a failure.
- Ideas are inputs to claude-advisor distillation only—not trade recommendations.
