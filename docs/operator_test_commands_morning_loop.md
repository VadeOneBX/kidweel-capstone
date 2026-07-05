# Operator test commands (morning loop order)

Commands assume repo root. Use **uv** on the host while **Docker Compose** publishes Redis (`6379`) and QOPS API (`8000`).

## Host + Docker (recommended)

Terminal 1 — runtime:

```bash
uv sync
cp .env.example .env   # once; keep REDIS_URL=redis://localhost:6379/0 on the host
docker compose up --build
```

Terminal 2 — tests and scripts (same repo, reads host `.env`):

```bash
uv sync
uv run pytest tests -q
uv run python scripts/cron_trigger.py --source manual --dry-run
curl -s http://localhost:8000/health | jq .
```

`uv run` uses the project venv and `pyproject.toml` pytest `pythonpath`; no manual `PYTHONPATH=src` on the host. Inside containers, cron still uses `PYTHONPATH=src` per `docker/crontab`.

**Canonical full suite:**

```bash
uv run pytest tests -q
```

**Canonical morning loop (not pytest):**

```bash
uv run python scripts/orb_morning_loop.py --mode manual --base-dir .
```

Chain in code: **ingestion wake** → **daily pipeline** (context → replay candidates → hydration expressions) → **risk guard** → **advisory brief** (`claude_brief` artifact) → optional **mobile notification** → **ORB manifest** updates. The morning loop does **not** submit paper orders.

**Surfaces:** Loop commands run on the operator runtime boundary. **Claude.ai desktop**, **Claude mobile**, and **Cursor mobile** may review loop artifacts or apply scoped repo edits—they do not trigger this chain unless the operator runs canonical commands on the host. **claude-advisor** (coordinator packet) emits separate `ADVISORY_*` labels; it does not replace the brief artifact.

Related operator docs: [operator_commands.md](./operator_commands.md), [evidence_artifacts_guide.md](./evidence_artifacts_guide.md), [mobile_infra_runbook.md](./mobile_infra_runbook.md).

---

## 0. Runtime / scheduler surface (parallel to the loop)

Optional Redis/FastAPI/cron scaffold for visibility and dry-run triggers—not part of `orb_morning_loop.py`.

| Test module | Role | Command |
|-------------|------|---------|
| `tests/test_runtime_health.py` | QOPS API `/health` and `/status` (paper-only posture); run on host while `docker compose` serves API | `uv run pytest tests/test_runtime_health.py -q` |

Operator paths (non-pytest, Docker up): `curl -s http://localhost:8000/health | jq .`, `uv run python scripts/cron_trigger.py --source manual --dry-run` — see [mobile_infra_runbook.md](./mobile_infra_runbook.md) and [operator_commands.md](./operator_commands.md).

---

## 1. Ingestion wake & ORB manifest

First step of `orb_morning_loop.py`: stage SpotGamma files, write run manifest, scheduler log lines.

| Test module | Role | Command |
|-------------|------|---------|
| `tests/test_morning_regime_intake.py` | File contracts, `run_ingestion_wake`, manifest paths, execution halt | `uv run pytest tests/test_morning_regime_intake.py -q` |

Operator alignment:

```bash
uv run python scripts/daily_ingestion_wake.py --mode manual --base-dir .
ls -lah data/spotgamma/raw/$(date +%F)
```

---

## 2. SpotGamma intake, normalization & context

`daily_pipeline`: staged files → normalized context corpus.

| Test module | Role | Command |
|-------------|------|---------|
| `tests/test_spotgamma_raw_session.py` | Raw session scoping, context corpus for replay | `uv run pytest tests/test_spotgamma_raw_session.py -q` |
| `tests/test_spotgamma_spy_excel.py` | SPY.xlsx context ingest (adjacent to scanner exports) | `uv run pytest tests/test_spotgamma_spy_excel.py -q` |
| `tests/test_reverse_vrp_field_normalization.py` | Reverse-VRP column normalization and symbol-context gates | `uv run pytest tests/test_reverse_vrp_field_normalization.py -q` |

---

## 3. Screening & replay candidate rows

`build_replay_candidates` and morning export enrichment inside `daily_pipeline`.

| Test module | Role | Command |
|-------------|------|---------|
| `tests/test_reverse_vrp_direction_score.py` | Reverse-VRP dealer direction scoring | `uv run pytest tests/test_reverse_vrp_direction_score.py -q` |
| `tests/test_guard_runner_contract.py` | Morning candidate export columns, replay audit classification, gamma hydrate joins (pipeline + guard shared) | `uv run pytest tests/test_guard_runner_contract.py -q` |

---

## 4. Dealer expression tier & structure economics

Dealer-weighted tiers and canonical spread construction (pipeline hydration and spread CLIs).

| Test module | Role | Command |
|-------------|------|---------|
| `tests/test_dealer_expression_tier.py` | Dealer tier → RR / PMP caps | `uv run pytest tests/test_dealer_expression_tier.py -q` |
| `tests/test_spread_builder.py` | Canonical spread builder + math gate | `uv run pytest tests/test_spread_builder.py -q` |
| `tests/test_spread_math.py` | Deterministic spread economics | `uv run pytest tests/test_spread_math.py -q` |
| `tests/test_spread_candidate_generator.py` | Spread candidates from staged quotes | `uv run pytest tests/test_spread_candidate_generator.py -q` |
| `tests/test_pmp_policy.py` | PMP → minimum R/R table | `uv run pytest tests/test_pmp_policy.py -q` |
| `tests/test_pmp_proxy.py` | Short-leg delta PMP proxy | `uv run pytest tests/test_pmp_proxy.py -q` |

---

## 5. Alpaca expression hydration (read-only, in pipeline)

`run_alpaca_expression_hydration` inside `daily_pipeline`—quotes/greeks fetch, no submit.

| Test module | Role | Command |
|-------------|------|---------|
| `tests/test_alpaca_hydration_loop.py` | Hydration loop, primary expression selection, artifacts | `uv run pytest tests/test_alpaca_hydration_loop.py -q` |
| `tests/test_alpaca_greeks_fetch_diagnostics.py` | Blueprint validation and empty-fetch staging | `uv run pytest tests/test_alpaca_greeks_fetch_diagnostics.py -q` |
| `tests/test_alpaca_greeks_paper_live.py` | Paper-live blueprint plan window (DTE), not morning submit | `uv run pytest tests/test_alpaca_greeks_paper_live.py -q` |
| `tests/test_paper_live_params.py` | Repo vs notebook paper-live parameter defaults | `uv run pytest tests/test_paper_live_params.py -q` |

---

## 6. Morning risk guard

Second major step after pipeline: `run_risk_guard` → `*_risk_audit.csv`.

| Test module | Role | Command |
|-------------|------|---------|
| `tests/test_guard_runner_contract.py` | *(also §3)* spread contract gaps, replay audit, hydration joins for guard input | *(same file as §3)* |
| `tests/test_am_note_gate.py` | AM-note macro gate, dealer structure, spread skeptic (risk/advisory boundary) | `uv run pytest tests/test_am_note_gate.py -q` |

Operator inspect after a run:

```bash
uv run python scripts/operator_status.py --base-dir .
```

---

## 7. Advisory overlay & post-ORB evidence

`generate_claude_brief` and Tier-3 idea distillation referenced in the brief—not approving transport.

| Test module | Role | Command |
|-------------|------|---------|
| `tests/test_operator_advisory.py` | Operator-facing advisory voice / acceptance fixtures | `uv run pytest tests/test_operator_advisory.py -q` |
| `tests/test_expression_frontier.py` | Expression frontier advisory and paper-gate withhold language | `uv run pytest tests/test_expression_frontier.py -q` |
| `tests/test_idea_distillation.py` | Post-ORB `*_ideas.json` distillation (votes, `AGENT_SIGNAL_WEAK`) | `uv run pytest tests/test_idea_distillation.py -q` |
| `tests/test_agents_as_tools_agility.py` | Typed specialist tools (advisory agility proof; no transport authority) | `uv run pytest tests/test_agents_as_tools_agility.py -q` |

Operator alignment:

```bash
cat data/advisory/latest_claude_brief.md
uv run python scripts/operator_status.py --base-dir . --ideas-summary
```

---

## 8. Notification & remote visibility

Morning loop ends with optional `send_mobile_notification` when not `--no-notify`. No dedicated pytest module; runtime notification settings are covered via QOPS API status (`test_runtime_health.py`) with Docker up, plus manifest/operator status workflows.

Operator alignment:

```bash
uv run python scripts/orb_morning_loop.py --mode manual --base-dir . --no-notify
cat data/notifications/latest_notification.json
tail -n 120 logs/ingestion_scheduler.log
```

---

## 9. Post-loop operator: WATCH promotion (no submit)

Separate from the morning loop; dry-run promotion review only.

| Test module | Role | Command |
|-------------|------|---------|
| `tests/test_watch_promotion.py` | WATCH expression operator promotion gate | `uv run pytest tests/test_watch_promotion.py -q` |

---

## 10. Post-loop: paper approval → payload → guardrails → transport

**Not** invoked by `orb_morning_loop.py`. Explicit operator packets and CLIs only; dry-run default.

| Test module | Role | Command |
|-------------|------|---------|
| `tests/test_paper_approval.py` | Paper approval candidate layer | `uv run pytest tests/test_paper_approval.py -q` |
| `tests/test_paper_payload_candidate.py` | Payload candidate build from approved rows | `uv run pytest tests/test_paper_payload_candidate.py -q` |
| `tests/test_guardrail_stack.py` | Blocking guardrail stack before HITL transport | `uv run pytest tests/test_guardrail_stack.py -q` |
| `tests/test_hitl_paper_transport.py` | Human-in-the-loop paper transport gate | `uv run pytest tests/test_hitl_paper_transport.py -q` |
| `tests/test_alpaca_paper_bridge.py` | Alpaca paper bridge (MCP-C12A), endpoint and credential safety | `uv run pytest tests/test_alpaca_paper_bridge.py -q` |

Targeted safety subset (from project footing):

```bash
uv run pytest tests/test_alpaca_paper_bridge.py tests/test_paper_closeout.py -q
```

---

## 11. Post-loop: closeout, pricing & order reconciliation

| Test module | Role | Command |
|-------------|------|---------|
| `tests/test_spread_close_pricing.py` | Spread close mid / quote fail-closed behavior | `uv run pytest tests/test_spread_close_pricing.py -q` |
| `tests/test_paper_closeout.py` | Paper closeout path and bridge integration | `uv run pytest tests/test_paper_closeout.py -q` |
| `tests/test_paper_order_status.py` | Order status audit from transport rows | `uv run pytest tests/test_paper_order_status.py -q` |
| `tests/test_paper_position_audit.py` | Filled-leg position audit (read-only broker posture in tests) | `uv run pytest tests/test_paper_position_audit.py -q` |

---

## 12. Offline research & backtest (outside morning loop)

Evidence refresh and threshold studies—no broker mutation in tests.

| Test module | Role | Command |
|-------------|------|---------|
| `tests/test_canonical_backtest_refresh.py` | BT-C3 canonical evidence refresh | `uv run pytest tests/test_canonical_backtest_refresh.py -q` |
| `tests/test_threshold_sweep.py` | THRESH-C1 offline threshold sweep | `uv run pytest tests/test_threshold_sweep.py -q` |

---

## 13. Bridge / export scaffolding (offline)

| Test module | Role | Command |
|-------------|------|---------|
| `tests/test_chain_snapshot_export.py` | Chain snapshot export (no live MCP in tests) | `uv run pytest tests/test_chain_snapshot_export.py -q` |

---

## Quick reference: loop phase → pytest files

| Morning loop phase | Test files (in suggested run order within phase) |
|--------------------|--------------------------------------------------|
| Runtime / cron (optional) | `test_runtime_health.py` |
| Wake + manifest | `test_morning_regime_intake.py` |
| Context / normalize | `test_spotgamma_raw_session.py`, `test_spotgamma_spy_excel.py`, `test_reverse_vrp_field_normalization.py` |
| Replay / screen | `test_reverse_vrp_direction_score.py`, `test_guard_runner_contract.py` |
| Structure / math | `test_dealer_expression_tier.py`, `test_spread_builder.py`, `test_spread_math.py`, `test_spread_candidate_generator.py`, `test_pmp_policy.py`, `test_pmp_proxy.py` |
| Hydration | `test_alpaca_hydration_loop.py`, `test_alpaca_greeks_fetch_diagnostics.py`, `test_alpaca_greeks_paper_live.py`, `test_paper_live_params.py` |
| Risk guard | `test_guard_runner_contract.py`, `test_am_note_gate.py` |
| Advisory | `test_operator_advisory.py`, `test_expression_frontier.py`, `test_idea_distillation.py`, `test_agents_as_tools_agility.py` |
| WATCH (post-loop) | `test_watch_promotion.py` |
| Paper path (post-loop) | `test_paper_approval.py`, `test_paper_payload_candidate.py`, `test_guardrail_stack.py`, `test_hitl_paper_transport.py`, `test_alpaca_paper_bridge.py`, `test_spread_close_pricing.py`, `test_paper_closeout.py`, `test_paper_order_status.py`, `test_paper_position_audit.py` |
| Offline / export | `test_canonical_backtest_refresh.py`, `test_threshold_sweep.py`, `test_chain_snapshot_export.py` |

**Run all modules in loop order (single command, long):**

```bash
uv run pytest \
  tests/test_runtime_health.py \
  tests/test_morning_regime_intake.py \
  tests/test_spotgamma_raw_session.py \
  tests/test_spotgamma_spy_excel.py \
  tests/test_reverse_vrp_field_normalization.py \
  tests/test_reverse_vrp_direction_score.py \
  tests/test_guard_runner_contract.py \
  tests/test_dealer_expression_tier.py \
  tests/test_spread_builder.py \
  tests/test_spread_math.py \
  tests/test_spread_candidate_generator.py \
  tests/test_pmp_policy.py \
  tests/test_pmp_proxy.py \
  tests/test_alpaca_hydration_loop.py \
  tests/test_alpaca_greeks_fetch_diagnostics.py \
  tests/test_alpaca_greeks_paper_live.py \
  tests/test_paper_live_params.py \
  tests/test_am_note_gate.py \
  tests/test_operator_advisory.py \
  tests/test_expression_frontier.py \
  tests/test_idea_distillation.py \
  tests/test_agents_as_tools_agility.py \
  tests/test_watch_promotion.py \
  tests/test_paper_approval.py \
  tests/test_paper_payload_candidate.py \
  tests/test_guardrail_stack.py \
  tests/test_hitl_paper_transport.py \
  tests/test_alpaca_paper_bridge.py \
  tests/test_spread_close_pricing.py \
  tests/test_paper_closeout.py \
  tests/test_paper_order_status.py \
  tests/test_paper_position_audit.py \
  tests/test_canonical_backtest_refresh.py \
  tests/test_threshold_sweep.py \
  tests/test_chain_snapshot_export.py \
  -q
```

(`test_guard_runner_contract.py` appears once in the ordered list; it spans pipeline enrichment and guard audit.)

---

## Boundary reminder

- Morning loop tests and commands remain **paper-only** and **non-submitting** unless you are explicitly in a scoped paper-transport packet.
- **Runtime vs implementation:** canonical commands (`uv run`, `orb_morning_loop.py`, `operator_status.py`) run on the host/SSH boundary. **Cursor mobile**, **Claude Code / Cursor Claude**, and **Claude.ai desktop** are implementation or review surfaces—they do not approve trades or replace operator shell commands.
- **Mobile visibility:** Tailscale, ntfy, and QOPS API routes are **read/dry-run only**. **Claude mobile** and **Cursor mobile** do not gain execution authority. See [tailscale_operator_access.md](./tailscale_operator_access.md) and [cursor_mobile_pack_contract.md](./cursor_mobile_pack_contract.md).
