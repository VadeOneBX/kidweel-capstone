# Kidweel GEX Automation

Kidweel GEX Automation is a paper-only options decision system that converts source-grounded market context into risk-defined trade candidates through deterministic guardrails, spread economics, and audit artifacts. Live trading is not supported. Transport defaults to **dry-run**; real Alpaca paper submit requires explicit operator opt-in (`--submit-paper`).

While it is true that automation can create substantial leverage, **deterministic guardrails** determine whether that leverage survives scale. This system aims to protect gains through **source-grounded context → spread economics → risk-defined execution policy → audit trail**.

## Public posture (30 seconds)

- **Live paper-trading validation** — Alpaca paper transport only; dry-run default; explicit operator opt-in (`--submit-paper`) to submit.
- **Defined-risk** — multileg spread candidates through deterministic spread economics and guardrails.
- **Deterministic gates** — EV/RR/PMP and policy gates decide continue, reject, or SKIP.
- **Evidence trails** — manifests, risk audits, transport records, and rejection reasons are first-class outputs.
- **Operator review** — advisory layers flag; gates approve; submit requires explicit flags and credentials.

**Public splash:** [kidweel-site/index.html](./kidweel-site/index.html) (GitHub Pages: publish the `kidweel-site/` folder)

## Subagency Proof

Kidweel demonstrates human-in-the-loop delegation for enterprise workflows.

Agents can inspect, classify, summarize, and propose.

Decision authority stays human.

The process records the handoff.

Agents assist. Humans decide. The process records why.

See: [`docs/subagency-proof.md`](docs/subagency-proof.md) · [Subagency map](./diagrams/kidweel_subagency_map.png) · [Splash](./kidweel-site/index.html)

---

## 1. Project Thesis

Options workflows fail in practice when checks drift—skipped gates, loose quotes, or advisory layers that start to sound like permission. Kidweel is an operator-built **decision trail**: 3-rd party data and related inputs become normalized context, deterministic gates decide what may continue, and only approved multileg payloads may reach Alpaca transport when you explicitly opt in.

Supporting layers (Claude briefs, subagent skills, ML-style advisory flags) help **candidate review** and interpretation. They do not approve trades, mutate thresholds, or submit orders.

---

## 2. Canonical Data Sources

| Source | Role in repo | Authority |
|--------|----------------|-----------|
| **SpotGamma exports** | Dealer positioning, volatility regime, walls, and directional constraints before spread economics | **Context only**—feeds ingestion and normalization; not a trade signal |
| **SPY backdrop context** | Regime label for morning replay hydration (when present) | Joined in risk guard; absent backdrop is advisory, not a silent upgrade |
| **Alpaca market data / greeks staging** | Option chain quotes, greeks staging, hydration expressions | **Infrastructure / reference**—Alpaca is used as a broker/data integration and options workflow reference point. It is not treated as a trading brain or discretionary signal source |
| **Operator-staged files** | `data/spotgamma/inbox`, dated raw session folders | Intake contract enforced at wake; rejects are logged on the manifest |

---

## 3. Architecture and decision flow

Canonical path (implemented modules and scripts; not every stage runs in every entrypoint):

```text
SpotGamma ingestion
  → context derivation (normalize / feature corpus)
  → symbol screening & replay rows (playbook / structure bias)
  → dealer direction scoring & tier gate (expression ranking)
  → spread builder & spread math (Option Alpha economics / EV when PMP exists)
  → optional advisory overlay (Claude brief, subagent skills—flags only)
  → risk guard (audit CSV + rejection reasons)
  → paper broker / executor (repo bridge, status audit, closeout—opt-in submit)
  → session runner (ORB morning loop: wake → pipeline → guard → brief → notify)
```

**Morning loop (primary operator path):** `scripts/orb_morning_loop.py` runs ingestion wake, `qops.pipeline.daily_pipeline` (context + candidates + Alpaca hydration expressions), `qops.risk.guard_runner`, then `qops.advisory.claude_brief` and optional notification. 

**Spread generation path (separate CLI):** `examples/generate_spread_candidates.py` reads staged Alpaca greeks CSV and emits spread candidates through `spread_math`—no transport.

**Run index:** `data/runs/<run_date>/orb_manifest.json` (latest) and `<run_id>_orb_manifest.json` (immutable snapshot) list artifact paths for that run.

<p align="center">
  <a href="./diagrams/system_operating_loop.svg">
    <img src="./diagrams/system_operating_loop.svg" alt="Operating loop: operator intent, advisory see-only, deterministic gates, paper transport execute" width="920"/>
  </a>
</p>

See also [docs/artifact_inspection_checklist.md](./docs/artifact_inspection_checklist.md) and [docs/evidence_artifacts_guide.md](./docs/evidence_artifacts_guide.md).

---

## 4. Execution Policy

The system is designed for **paper execution and auditability**. Live trading is not recommended.

| Policy | Repo behavior |
|--------|----------------|
| **Bull call spreads (and other canonical verticals)** | May continue through spread math, risk guard, paper approval, and payload build toward **automated paper execution** when gates pass and the operator opts in |
| **Long calls** | May appear in context (`LONG_CALL_PARKED` / parked bias); playbook policy **downgrades to SKIP** for canonical execution—they stay **parked for review**, not unattended single-leg submit |
| **Live trading** | Forbidden—`scripts/orb_morning_loop.py` rejects `--live`; capstone rules forbid live Alpaca transport URL |
| **Dry-run default** | Paper bridge and closeout default to dry-run; `--submit-paper` required for real paper submit |
| **Unattended “AI” execution** | Not supported—submit and close require explicit flags, credentials, and packet scope |

Canonical executable structures: `BULL_CALL_SPREAD`, `BEAR_PUT_SPREAD`, `BULL_PUT_CREDIT_SPREAD`, `BEAR_CALL_CREDIT_SPREAD`, or `SKIP`. Details: [docs/system-identity.md](./docs/system-identity.md).

Paper path docs: [alpaca paper bridge](./docs/alpaca-paper-bridge.md), [paper approval candidates](./docs/paper-approval-candidates.md), [paper payloads](./docs/paper-payload-candidates.md), [order status audit](./docs/paper-order-status-audit.md), [paper closeout](./docs/paper-closeout.md).

---

## 5. Evidence and replay (operator)

Runs should preserve context, guard outcomes, and rejection or approval reasons in manifests and audit CSVs. Rejected candidates are first-class evidence.

Operator depth: [evidence artifacts guide](./docs/evidence_artifacts_guide.md), [backtest evidence status](./docs/backtest_evidence_status.md), [claude-backtest-wiring](./docs/claude-backtest-wiring.md).

---

## 6. Paper-Trade Guardrails

- **Paper-only execution path** with fail-closed gates (`paper_only=True` in risk guard).
- **Manifest flags:** `live_mode_enabled` and `broker_mutation_occurred` should remain false for morning runs unless an explicit, scoped paper packet says otherwise.
- **Schemas and playbooks are contracts**—do not re-derive protected fields (`regime_label`, `confidence`, `gamma_ratio`) in automation.
- **Alpaca paper transport:** `ALPACA_PAPER_*`, base URL `https://paper-api.alpaca.markets` only; deterministic `client_order_id` from payload id.
- **MCP:** transport contract scaffold (C10A) and offline mock (C11A)—not broker judgment.
- **Subagents / skills:** bounded delegates; same validation path as the deterministic core ([subagency proof](./docs/subagency-proof.md), [AGENTS.md](./AGENTS.md)).

Governance: [docs/c13-governance.md](./docs/c13-governance.md), [CLAUDE.md](./CLAUDE.md).

---

## 7. Fallback / Manual Review Path

When automation stops (intake reject, hydration gap, guard reject, or WATCH expression):

1. Read **`data/runs/<run_date>/<run_id>_orb_manifest.json`** for artifact paths and errors.
2. Inspect **candidates**, **expressions**, and **`data/processed/risk/<run_id>_risk_audit.csv`**—reject reasons are first-class evidence.
3. Read **`data/advisory/<run_id>_claude_brief.md`** (advisory summary from artifacts—not approval).
4. **WATCH promotion:** operator-only `scripts/review_watch_expression.py` may set `paper_route_status=PAPER_REVIEW_READY` in a review CSV; it does **not** submit orders.
5. **Paper submit** remains a separate explicit step: `examples/submit_paper_payload_candidates.py` (dry-run unless `--submit-paper`).

Operator commands: [docs/operator_commands.md](./docs/operator_commands.md).

---

## 8. Derivatives Disclaimer
**Not** a signal service, trading advice, AI trading bot, or autonomous trading system. Options trading carries a very high level of risk and is not suitable for all. Past performance and strategic posture within this repo make no claim or guarantee of future results.

---

## 9. Public readiness and license

This repository is capstone / portfolio work, not a production trading product. **Paper-only** posture and **dry-run** defaults are binding. **No MIT** or other permissive default license is checked in.

- **Rights:** [NOTICE](./NOTICE) — all rights reserved unless a future governance packet adds explicit terms.
- **Viewer guide:** [docs/public_readiness.md](./docs/public_readiness.md).
- **Helper inventory (no deletions):** [docs/repo_classification_C1.md](./docs/repo_classification_C1.md).

Before sharing artifacts externally, run the privacy grep in [docs/claude_code_access_runbook.md](./docs/claude_code_access_runbook.md).

---

## Repository navigation

| Area | Doc |
|------|-----|
| System identity & structure policy | [docs/system-identity.md](./docs/system-identity.md) |
| Evidence map | [docs/evidence_artifacts_guide.md](./docs/evidence_artifacts_guide.md) |
| Backtest / replay evidence status | [docs/backtest_evidence_status.md](./docs/backtest_evidence_status.md) |
| Public readiness | [docs/public_readiness.md](./docs/public_readiness.md) |
| Repo classification (CLEAN-C1) | [docs/repo_classification_C1.md](./docs/repo_classification_C1.md) |
| Morning artifact checklist | [docs/artifact_inspection_checklist.md](./docs/artifact_inspection_checklist.md) |
| Subagency proof | [docs/subagency-proof.md](./docs/subagency-proof.md) |
| Subagent governance | [docs/subagent-governance.md](./docs/subagent-governance.md) |
| Claude advisor (proposal only) | [docs/claude-advisor-context.md](./docs/claude-advisor-context.md) |
| Alpaca MCP integration | [integrations/alpaca_mcp/README.md](./integrations/alpaca_mcp/README.md) |

**Tests (canonical):**

```bash
PYTHONPATH=src python -m pytest tests -q
```

**Paper path**

<p>
  <a href="./docs/alpaca-paper-bridge.md"><img src="https://img.shields.io/badge/Paper_bridge-1e3a5f?style=for-the-badge" alt="Alpaca paper bridge"/></a>
  <a href="./docs/paper-closeout.md"><img src="https://img.shields.io/badge/Mleg_closeout-1e3a5f?style=for-the-badge" alt="Paper closeout"/></a>
  <a href="./docs/paper-order-status-audit.md"><img src="https://img.shields.io/badge/Order_status_audit-1e3a5f?style=for-the-badge" alt="Order status audit"/></a>
  <a href="./docs/notebook-alignment.md"><img src="https://img.shields.io/badge/Notebook_alignment-1e3a5f?style=for-the-badge" alt="Notebook alignment"/></a>
</p>

**Claude & advisory**

<p>
  <a href="./docs/claude-advisor-context.md"><img src="https://img.shields.io/badge/Claude_advisor-4c1d95?style=for-the-badge" alt="Claude advisor context"/></a>
  <a href="./docs/advisory-group-matrix.md"><img src="https://img.shields.io/badge/Advisory_groups-4c1d95?style=for-the-badge" alt="Advisory group matrix"/></a>
  <a href="./docs/evidence_artifacts_guide.md"><img src="https://img.shields.io/badge/Evidence_artifacts-4c1d95?style=for-the-badge" alt="Evidence artifacts guide"/></a>
  <a href="./docs/claude-overlay.md"><img src="https://img.shields.io/badge/Claude_overlay-4c1d95?style=for-the-badge" alt="Claude overlay"/></a>
  <a href="./docs/claude-backtest-wiring.md"><img src="https://img.shields.io/badge/Claude_backtest-4c1d95?style=for-the-badge" alt="Claude backtest wiring"/></a>
</p>

**Integrations & diagrams**

<p>
  <a href="./integrations/alpaca_mcp/README.md"><img src="https://img.shields.io/badge/Alpaca_MCP-14532d?style=for-the-badge" alt="Alpaca MCP README"/></a>
  <a href="./integrations/alpaca_mcp/transport_contract.md"><img src="https://img.shields.io/badge/C10A_transport-14532d?style=for-the-badge" alt="C10A transport contract"/></a>
  <a href="./diagrams/claude_context_layer.md"><img src="https://img.shields.io/badge/Context_layer-14532d?style=for-the-badge" alt="Context layer"/></a>
  <a href="./diagrams/system_operating_loop.svg"><img src="https://img.shields.io/badge/System_loop_diagram-14532d?style=for-the-badge" alt="System operating loop SVG"/></a>
</p>
