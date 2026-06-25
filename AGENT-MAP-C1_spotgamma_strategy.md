# Agent map C1 — SpotGamma strategy lanes (compact A)

**Packet:** ENTERPRISE-WORKFLOW-C1. **Authority:** [docs/c13-governance.md](docs/c13-governance.md) → [docs/system-identity.md](docs/system-identity.md) → this map. **Corrections:** [AGENT-MAP-C1a_corrections.md](AGENT-MAP-C1a_corrections.md) supersedes this file on conflict.

This map names **who may act** in the Kidweel paper-only workflow and how **SpotGamma scanner profiles** feed deterministic stages—not a swarm of trading agents.

---

## Map A — Actors vs pipeline (compact)

```text
Coordinator (human)
  ├─ delegates → Cursor (repo edits, verification)
  ├─ delegates → Claude / claude-advisor (ADVISORY_* only)
  ├─ delegates → Subagent skills (memos: repo-cleaner, safety-auditor, …)
  └─ approves → paper transport packets (explicit opt-in)

Deterministic repo (qops)
  ingestion → daily_pipeline → hydration loop → spread math → risk guard → payload build

MCP / paper bridge
  narrow integration on coordinator-gated transport only
```

| Actor | Sees | Acts |
|-------|------|------|
| **Coordinator** | Manifests, audit CSVs, handoffs | Scope, approval, WATCH promotion |
| **Cursor** | Full repo in packet | Mutate scoped files; run pytest |
| **Claude Code** | Runbook-scoped paths | Audit, advise, draft; **no** `--submit-paper` |
| **claude-advisor skill** | Reference docs + supplied context | `ADVISORY_*` flags |
| **Subagent skills** | Skill reference docs | Single report; no spawn |
| **Deterministic `qops`** | Staged data | Gates, classifications, audits |
| **MCP** | Repo-gated requests | Read/submit integration results only when packet allows |

**Doctrine:** Agents increase **review coverage**; they do not replace judgment or move orders.

---

## Map A — SpotGamma `source_profile` → workflow stage

From [docs/spotgamma-to-replay.md](docs/spotgamma-to-replay.md) (context only; not trade signals):

| `source_profile` | Stage role | Emits trade candidates? |
|------------------|------------|-------------------------|
| `spy_history`, `spy_excel` | SPY backdrop / regime join | No (context by `trade_date`) |
| `squeeze` | Scanner row → replay candidate | Yes (subject to gates) |
| `vrp` | Volatility risk premium scanner | Yes |
| `reverse_vrp` | Reverse VRP scanner | Yes (SPY context rules differ) |
| `processed_weekly` | Weekly processed scanner | Yes |

Downstream (same for all profiles that survive intake):

```text
replay / daily_pipeline row
  → dealer direction score & tier (A–E)
  → alpaca hydration expressions (PRIMARY / WATCH / FAILED)
  → spread builder (canonical structures only)
  → risk guard → risk_audit.csv
  → claude_brief.md (summary, not approval)
```

---

## Advisory group names (interpretive only)

Aligned with [docs/advisory-group-matrix.md](docs/advisory-group-matrix.md) stubs—**labels for claude-advisor**, not approval routing:

| Advisory group | Typical `source_profile` anchor |
|----------------|----------------------------------|
| `SQUEEZE_CANDIDATES` | `squeeze` |
| `VOLATILITY_RISK_PREMIUM` | `vrp` |
| `REVERSE_RISK_PREMIUM` | `reverse_vrp` |

Coordinator attaches context; advisor picks **one** primary group when asked. Gates still own accept/reject.

---

## Canonical executable structures (repo contract)

Spread builder emit set: `BULL_CALL_SPREAD`, `BEAR_PUT_SPREAD`, `BULL_PUT_CREDIT_SPREAD`, `BEAR_CALL_CREDIT_SPREAD`, `SKIP`. `LONG_GAMMA_HEDGE` is non-executable. Capstone sprint execution focus: **bull call spread** in paper mode when gates pass.

---

## Evidence pointers

| Question | Where to look |
|----------|----------------|
| Accept/reject per symbol? | `data/processed/risk/<run_id>_risk_audit.csv` |
| Advisory summary? | `data/advisory/<run_id>_claude_brief.md` |
| Run artifact index? | `data/runs/<run_date>/<run_id>_orb_manifest.json` |
| Full evidence guide | [docs/evidence_artifacts_guide.md](docs/evidence_artifacts_guide.md) |
