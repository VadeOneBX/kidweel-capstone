# Evidence artifacts guide (ENTERPRISE-WORKFLOW-C1)

Kidweel treats **rejected candidates as first-class evidence**. A useful run preserves source context, spread construction, guard outcome, advisory summary, and (when scoped) paper transport audits—not a win/loss headline.

**Related:** [artifact_inspection_checklist.md](./artifact_inspection_checklist.md), [workflow-ownership.md](./workflow-ownership.md), [claude-advisor-context.md](./claude-advisor-context.md), [paper-order-status-audit.md](./paper-order-status-audit.md).

---

## Capstone framing (one paragraph)

Kidweel is **enterprise workflow automation** for a paper-only options desk: ingestion and normalization produce auditable candidates; deterministic spread economics and risk gates approve or reject; optional agent layers widen **review coverage** without owning judgment. Candidate selection, spread construction, risk checks, paper execution, and broker reconciliation stay **separated** so failures remain observable and reversible. This is not an autonomous AI trader—it is a constraint-survivable decision trail with explicit human supervision at approval and transport.

---

## Workflow diagram (README-aligned)

Canonical loop (same as [README.md](../README.md)):

```text
SpotGamma ingestion
  → context derivation
  → symbol screening / replay rows
  → dealer direction & tier gate
  → spread builder & spread math (EV when PMP exists)
  → optional advisory overlay (flags / brief only)
  → risk guard (risk audit CSV)
  → paper broker / executor (dry-run default; opt-in submit)
  → session runner (morning loop)
```

Visual: [diagrams/system_operating_loop.svg](../diagrams/system_operating_loop.svg).

**Bounded delegation:** Agent work → Gate → Human review → Decision → Audit.

---

## Human determinism note

| Layer | Decides | Does not decide |
|-------|---------|-----------------|
| **Deterministic repo** (`qops.*`) | Playbook policy, spread math, RR/PMP gates, payload shape, audit columns | Discretionary ticker picks, narrative overrides |
| **Operator** (human) | Packet scope, paper transport opt-in, WATCH promotion; runs canonical runtime commands | — |
| **claude-advisor** (skill/subagent) | `ADVISORY_*` labels, memos from **supplied** context | Approve, size, submit, gate changes |
| **Advisory agents** (repo-cleaner, safety-auditor, etc.) | Typed review reports within skill scope | Approval, transport, spawn subagents |
| **Claude.ai desktop / Claude mobile** | Artifact review; future allowlisted command triggering (desktop only, when wired) | Approve, size, submit, bypass gates, arbitrary shell |
| **Claude Code / Cursor Claude / Cursor mobile** | Scoped repo edits and diff review in coordinator packets | Approve, size, submit, transport |
| **MCP / paper bridge** | Narrow integration responses when repo-gated | Approval or payload construction |

Protected fields (`regime_label`, `confidence`, `gamma_ratio`) are **not** re-derived in automation. `SKIP` remains `SKIP`. `structure_bias` is not upgraded by advisory output.

---

## Swarm prevention (required language)

1. **Only the coordinator delegates** agents and skills.
2. **Subagents do not spawn subagents.**
3. **Adding agents does not change the approval path:** propose → deterministic validator → risk gate → transport → audit.
4. **No advisory output becomes a payload.** `ADVISORY_*` and morning briefs inform review; they do not short-circuit `paper_approval` or transport.
5. **The repo is the message bus**—handoffs under `docs/handoffs/`, not chat continuity.

See [subagent-governance.md](./subagent-governance.md) and [subagency-proof.md](./subagency-proof.md).

---

## Artifact chain per run

| Stage | Artifact | Typical path |
|-------|----------|----------------|
| Run index | ORB manifest | `data/runs/<run_date>/<run_id>_orb_manifest.json` (latest: `orb_manifest.json`) |
| Context | Normalized / feature corpus | manifest `context_artifact` |
| Candidates | Replay or spread rows | manifest `candidates_artifact` |
| Hydration | Expressions + dealer tiers | `data/processed/<run_id>_alpaca_hydration_expressions.csv` |
| **Tier 3 ideas (optional)** | Post-ORB subagent ideas | `data/runs/<run_date>/<run_id>_<agent>_ideas.json` |
| **Risk guard (accept/reject)** | Morning risk audit | `data/processed/risk/<run_id>_risk_audit.csv` |
| **Advisory evidence** | Deterministic brief + distilled votes | `data/advisory/<run_id>_claude_brief.md`, `latest_claude_brief.md` |
| WATCH operator | Promotion review (no submit) | `data/processed/runs/<run_id>/watch_promotion_review.csv` |
| Paper payloads | Ready rows (separate CLI) | `data/processed/paper_payload_candidates.csv` (when built) |
| Paper transport | Submit audit | transport CLI output + bridge audits |
| Reconciliation | Order status | `data/processed/paper_order_status_audit.csv` |

Morning entrypoint: `scripts/orb_morning_loop.py` (does **not** submit). Remote inspection: `scripts/operator_status.py --run-id <id>`. Post-ORB idea counts: `scripts/operator_status.py --ideas-summary`. Read-only chain: `scripts/alpaca_fetch.py` (see [skills/alpaca-cli-skills.md](./skills/alpaca-cli-skills.md)). Connectors (Tailscale, ntfy, Docker cron): [connectors_c1_runbook.md](./connectors_c1_runbook.md).

---

## Advisory evidence format

Two complementary layers—both **non-approving**:

### A. Morning brief (artifact-generated)

Produced by `qops.advisory.claude_brief` after risk guard. Sections:

- Run metadata (`run_id`, `status`, `mode`)
- Intake counts (staged / rejected files)
- **Risk classification** aggregates from `summarize_risk_audit` (approved, parked, context gate rejects, hydration lanes, dealer tier counts)
- Top rejection reasons (from audit CSV)
- Guardrails (`live_mode_enabled`, `broker_mutation_occurred`—must be false for standard morning runs)
- **Advisory** disclaimer: context from artifacts; operator reviews paths; no live path
- Pointers to context, candidates, expressions, risk audit paths
- **Post-ORB idea distillation** (when `*_ideas.json` present): ranked policy votes (`vote:`, `ev_check:`, `regime_alignment:`); `AGENT_SIGNAL_WEAK` flags

### B. claude-advisor skill (coordinator packet)

When the coordinator invokes the **claude-advisor** skill (not the morning brief artifact), emit **one primary label** per review ([claude-advisor-context.md](./claude-advisor-context.md)). If the brief already lists policy votes, interpret them—do not re-run EV or change `vote:` outcomes.

| Label | Meaning |
|-------|---------|
| `ADVISORY_OK` | Continue analysis; no elevated caution |
| `ADVISORY_CAUTION` | Tighten human review |
| `ADVISORY_DOWNGRADE` | Lower confidence / stricter posture |
| `ADVISORY_SKIP` | No structural continuation on supplied context |

Optional short memo; no sizing, no submit language. Store handoff responses under `docs/handoffs/` per [workflow-ownership.md](./workflow-ownership.md).

---

## Accept / reject audit table (risk guard)

Source of truth: `data/processed/risk/<run_id>_risk_audit.csv` (`guard_runner`, provenance `guard_c1f_morning_risk_audit`).

### Outcome families

| `classification` / `paper_approval_status` | Operator meaning | Counts as capstone evidence |
|--------------------------------------------|------------------|------------------------------|
| `APPROVED_PAPER` / `APPROVED_FOR_PAPER_REVIEW` | Passed deterministic gates; eligible for **separate** payload/transport packet | Accept path |
| `REJECTED_RR` | Reward/risk or spread math gate | Reject path |
| `REJECTED_PMP` | PMP / probability / EV gate | Reject path |
| `REJECTED_LIQUIDITY` | Quote / liquidity sanity | Reject path |
| `REJECTED_MISSING_FIELDS` / `INCOMPLETE` | Required fields absent | Reject path |
| `REJECTED_POLICY` | Playbook / structure policy | Reject path |
| `CONTEXT_BLOCKED` / `CONTEXT_INCOMPLETE` | Context gate before spread economics | Reject / incomplete path |
| `PARKED_REVIEW`, hydration loop statuses (`HYDRATION_PENDING`, `WATCH_EXPRESSION_AVAILABLE`, etc.) | Not approved for transport; may need data or operator WATCH review | Parked evidence |

### Key columns (audit row)

| Column | Role |
|--------|------|
| `run_id`, `symbol` | Traceability |
| `structure`, legs, strikes, `debit`/`credit`, `max_loss`, `rr_actual`, `pmp`, `ev` | Spread economics evidence |
| `reject_reason` | Machine-readable gate reason (prefixes e.g. `context_gate:`, `spread_economics:`) |
| `classification` | Roll-up label for reporting |
| `context_gate_status`, `context_gate_reason` | Pre-spread context gate |
| `candidate_loop_status`, `hydration_status` | Hydration lane (not a separate “agent”) |
| `dealer_gate_tier`, `dealer_weighted_score` | Direction / tier evidence |
| `selection_reason`, `data_gap_reason` | Why a row stopped or parked |

Full column list matches `_RISK_AUDIT_COLUMNS` in `src/qops/risk/guard_runner.py` plus `C2A_EVIDENCE_COLUMNS` from `src/qops/pipeline/alpaca_hydration_loop.py`.

### Quick accept/reject rollup (CLI)

```bash
python - <<'PY'
import pandas as pd
from pathlib import Path
run_id = "REPLACE_RUN_ID"
p = Path(f"data/processed/risk/{run_id}_risk_audit.csv")
if not p.is_file():
    raise SystemExit(f"missing {p}")
df = pd.read_csv(p)
col = "classification" if "classification" in df.columns else "paper_approval_status"
print(df[col].value_counts().to_string())
print("--- rejects (sample) ---")
rej = df[df[col].astype(str).str.contains("REJECT|BLOCK|INCOMPLETE", na=False)]
print(rej[["symbol", col, "reject_reason"]].head(20).to_string(index=False))
PY
```

---

## Paper transport evidence (optional packet)

Not part of the morning loop by default.

| Step | Evidence |
|------|----------|
| Dry-run transport | CLI stdout; no broker mutation |
| `--submit-paper` | Bridge audit records; deterministic `client_order_id` |
| Post-submit | `examples/check_paper_order_status.py` → `paper_order_status_audit.csv` |

See [alpaca-paper-bridge.md](./alpaca-paper-bridge.md), [paper-payload-candidates.md](./paper-payload-candidates.md).

---

## Privacy before external share

Run the grep in [claude_code_access_runbook.md](./claude_code_access_runbook.md) on `data/processed/`, `docs/audit/`, `data/advisory/`, `data/runs/`. Never paste `.env` or credential-like strings.

---

## Sprint scope reminder (capstone)

| In scope | Out of scope |
|----------|----------------|
| Bull call spreads (canonical vertical) | Live trading, credit spreads, iron condors |
| Paper dry-run default; opt-in submit | LLM discretionary trade selection |
| Advisory accept/reject + audit CSV | Expanded backtesting claims |

Cheap underlyings (e.g. NIO, BB) are **candidates only**—they must still pass spread economics, bid/ask sanity, PMP/RR, max loss, and paper-only approval.

Paper BCS operator path: [paper_bull_call_c1_runbook.md](./paper_bull_call_c1_runbook.md). Latest recorded outcomes: [audit/paper_bull_call_c1_evidence.md](./audit/paper_bull_call_c1_evidence.md).
