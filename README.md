# Kidweel GEX Automation

**Paper-only decision infrastructure.** Kidweel GEX Automation is a paper-only options decision system that converts source-grounded market context into risk-defined trade candidates through deterministic guardrails, spread economics, and audit artifacts. Live trading is not supported. Transport defaults to **dry-run**; real Alpaca paper submit requires explicit operator opt-in (`--submit-paper`).

Claude proposes. The system decides. Transport executes.

---

## 1. Project Thesis

Options workflows fail in practice when checks drift—skipped gates, loose quotes, or advisory layers that start to sound like permission. Kidweel is an operator-built **paper-only decision trail**: SpotGamma and related inputs become normalized context, deterministic gates decide what may continue, and only approved multileg payloads may reach Alpaca **paper** transport when you explicitly opt in.

Automation creates leverage. **Deterministic guardrails** determine whether that leverage survives scale. This is not market prediction or a discretionary signal engine; it is **source-grounded context → spread economics → risk-defined execution policy → audit trail**.

Supporting layers (Claude briefs, subagent skills, ML-style advisory flags) help **candidate review** and interpretation. They do not approve trades, mutate thresholds, or submit orders.

---

## 2. Canonical Data Sources

| Source | Role in repo | Authority |
|--------|----------------|-----------|
| **SpotGamma exports** | Dealer positioning, volatility regime, walls, and directional constraints before spread economics | **Context only**—feeds ingestion and normalization; not a trade signal |
| **SPY backdrop context** | Regime label for morning replay hydration (when present) | Joined in risk guard; absent backdrop is advisory, not a silent upgrade |
| **Alpaca market data / greeks staging** | Option chain quotes, greeks staging, hydration expressions | **Infrastructure / reference**—Alpaca is used as a broker/data integration and options workflow reference point. It is not treated as a trading brain or discretionary signal source |
| **Operator-staged files** | `data/spotgamma/inbox`, dated raw session folders | Intake contract enforced at wake; rejects are logged on the manifest |

SpotGamma-derived context is used to describe dealer positioning, volatility regime, and directional constraints before any spread economics are evaluated.

---

## 3. Architecture Flow

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

**Morning loop (primary operator path):** `scripts/orb_morning_loop.py` runs ingestion wake, `qops.pipeline.daily_pipeline` (context + candidates + Alpaca hydration expressions), `qops.risk.guard_runner`, then `qops.advisory.claude_brief` and optional notification. It does **not** submit paper orders.

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

The system is designed for **paper execution and auditability**. Live trading is not supported.

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

## 5. Evidence and Backtesting

**What counts as evidence:** replay and morning-run **CSVs**, **risk audit** rows (including rejects), **orb manifests**, **hydration expression** files, **paper transport** records, and deterministic gate reasons. A successful run does not require paper submission. A useful run must preserve source context, candidate construction, guard outcome, and rejection or approval reason.

**Rejected candidates are evidence.** They show guard behavior, missing-field handling, spread economics failure, and policy enforcement.

**Backtesting / replay in repo:**

- **Replay aggregation:** `src/qops/backtest/runner.py` (`run_iterative_backtest`) aggregates **ReplayContext** rows (PnL and exits supplied by context—not a live broker loop).
- **SpotGamma → replay candidates:** `spotgamma_replay_builder`, daily pipeline exports.
- **Alpaca replay planning:** `alpaca_replay_inputs.py` plans historical data needs—no orders.
- **Mock research memos:** `docs/backtests/`, `docs/audit/`, `docs/reconciliation/mock_backtest_reconciliation_C1.md` document **synthetic** PnL and strikes—useful for inspection, not proof of edge.

There is no checked-in `alpaca_iterative_backtester.py` in this repository. Treat any external iterative backtest helper that fabricates Sharpe or PnL with random placeholders as **legacy/scaffold**, not final evidence infrastructure.

Legacy or scaffolded backtesting utilities are retained only where useful for inspection or development. Evidence claims should come from replay artifacts, risk audits, paper transport records, and deterministic candidate outputs—not randomized placeholder metrics.

Research-only Claude overlay comparisons: [docs/claude-backtest-wiring.md](./docs/claude-backtest-wiring.md), [docs/findings-c13-claude-context.md](./docs/findings-c13-claude-context.md).

---

## 6. Paper-Only Guardrails

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

## 8. What This Is Not

- Not **live execution** or production trading on live Alpaca endpoints.
- Not an **autonomous AI trading** system, **AI trading brain**, **self-directed trading agent**, or **fully automated options trader**.
- Not a **predictive alpha engine** or **guaranteed edge** product.
- Not unrestricted order submission—no blind auth retry, no assistant with cancel/replace authority.
- Not proof that mock backtest memos or placeholder metrics represent real PnL.

It **is** paper-only decision infrastructure with deterministic guardrails, source-grounded context, spread economics, audit trail, and explicit candidate review before any paper transport.

---

## Repository navigation

| Area | Doc |
|------|-----|
| System identity & structure policy | [docs/system-identity.md](./docs/system-identity.md) |
| Evidence map | [docs/evidence_artifacts_guide.md](./docs/evidence_artifacts_guide.md) |
| Morning artifact checklist | [docs/artifact_inspection_checklist.md](./docs/artifact_inspection_checklist.md) |
| Subagent governance | [docs/subagent-governance.md](./docs/subagent-governance.md) |
| Claude advisor (proposal only) | [docs/claude-advisor-context.md](./docs/claude-advisor-context.md) |
| Alpaca MCP integration | [integrations/alpaca_mcp/README.md](./integrations/alpaca_mcp/README.md) |

**Tests (canonical):**

```bash
PYTHONPATH=src python -m pytest tests -q
```
