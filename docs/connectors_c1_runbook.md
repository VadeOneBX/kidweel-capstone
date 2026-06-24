# Connectors C1 runbook (CONNECTORS-C1)

**Goal:** Stabilize how the operator **runs**, **schedules**, and **inspects** the Kidweel paper-only workflow from the desk or remotely—without live trading, without secrets in git, and without treating MCP or agents as approval.

**Related:** [operator_commands.md](./operator_commands.md), [evidence_artifacts_guide.md](./evidence_artifacts_guide.md), [claude_code_access_runbook.md](./claude_code_access_runbook.md), [alpaca-paper-bridge.md](./alpaca-paper-bridge.md).

---

## Connector layers (sprint map)

| Layer | Role in this repo | Repo truth |
|-------|-------------------|------------|
| **Docker / OrbStack** | Optional host for scheduled morning loop (`/app` layout in cron templates) | [infra/crontab](../infra/crontab), [infra/docker/crontab_spy_store](../infra/docker/crontab_spy_store) |
| **Redis** | Optional future queue/state bridge | **Not wired** — run state is **file-based** (manifests, CSVs, logs) |
| **Tailscale** | Encrypted path to the Mac/host that owns the repo and `.env` | Operator deployment (SSH); commands below |
| **Alpaca MCP / CLI** | Paper transport and read-only status | Bridge CLI + diagnostics; MCP scaffold in [integrations/alpaca_mcp/README.md](../integrations/alpaca_mcp/README.md) |
| **Repo scripts** | Ingestion, guard, advisory, optional submit/reconcile | `scripts/*`, `examples/*` |

---

## Acceptance test (remote operator)

From a phone or remote desktop, you should be able to:

1. **See** the latest run (`operator_status` or manifest JSON).
2. **See** advisory summary (`latest_claude_brief.md` or notification JSON).
3. **See** paper transport posture (`broker_mutation_occurred: false` on morning runs unless a paper packet ran).
4. **Trigger** a manual morning loop on the host (SSH) or rely on scheduler + **ntfy/Pushover** ping when complete.

You do **not** need Redis or Docker for this acceptance path if the workflow runs on the host with a venv.

---

## Baseline local setup

### 1. Repository and Python

```bash
cd /path/to/kidweel-capstone
python3 -m venv .venv
source .venv/bin/activate
pip install -e .   # or project’s documented install
```

### 2. Credentials (never commit)

```bash
cp .env.example .env
# Edit .env locally — never cat .env in chat or logs
```

| Variable set | Used for |
|--------------|----------|
| `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` | Market data / greeks hydration (read-oriented) |
| `ALPACA_PAPER_*` + `ALPACA_PAPER_BASE_URL` | Paper **submit** and order status only (`https://paper-api.alpaca.markets`) |

Market-data keys must **not** be reused silently for paper transport.

### 3. Execution halt (fail-closed)

```bash
touch data/.execution_halt    # block transport paths that respect halt
rm data/.execution_halt       # resume
```

---

## Daily workflow (canonical scripts)

| Step | Command | Broker mutation? |
|------|---------|------------------|
| Wake only | `PYTHONPATH=src python scripts/daily_ingestion_wake.py --mode manual --base-dir .` | No |
| **Full morning loop** | `PYTHONPATH=src python scripts/orb_morning_loop.py --mode manual --base-dir .` | No |
| Loop without push | add `--no-notify` | No |
| **Status / remote inspect** | `PYTHONPATH=src python scripts/operator_status.py --base-dir .` | No |
| Status by run | `PYTHONPATH=src python scripts/operator_status.py --run-id <run_id>` | No |
| WATCH review (dry-run default) | `PYTHONPATH=src python scripts/review_watch_expression.py ...` | No submit |

Morning loop chain (in code): wake → `daily_pipeline` → `run_risk_guard` → `generate_claude_brief` → optional `send_mobile_notification`.

Scheduler template (container paths):

```cron
# infra/crontab — America/New_York, weekdays
# orb-watchdog: 9:00–9:45 every 15m
# orb-final: 10:00
```

Install on the host or map into a container with repo mounted at `/app` and `logs/` writable.

---

## Remote inspection

### A. Tailscale + SSH (primary)

1. Install [Tailscale](https://tailscale.com/) on the Mac that holds the repo.
2. From remote shell:

```bash
ssh <tailscale-host> 'cd /path/to/kidweel-capstone && source .venv/bin/activate && PYTHONPATH=src python scripts/operator_status.py'
```

3. Advisory text:

```bash
ssh <tailscale-host> 'tail -n 80 /path/to/kidweel-capstone/data/advisory/latest_claude_brief.md'
```

4. Latest notification payload (includes `advisory_artifact`, flags):

```bash
ssh <tailscale-host> 'cat /path/to/kidweel-capstone/data/notifications/latest_notification.json'
```

5. Risk audit path comes from manifest `risk_audit_artifact`; roll up classifications per [evidence_artifacts_guide.md](./evidence_artifacts_guide.md).

### B. Mobile push (no SSH)

Set **one** of these on the **host** that runs the morning loop (values stay in env, not in git):

| Env | Effect |
|-----|--------|
| `KIDWEEL_NTFY_TOPIC` (+ optional `KIDWEEL_NTFY_SERVER`, default `https://ntfy.sh`) | POST summary when loop completes |
| `KIDWEEL_PUSHOVER_TOKEN` + `KIDWEEL_PUSHOVER_USER` | Pushover message |
| (macOS only) | Falls back to `osascript` notification if ntfy/Pushover unset |

Subscribe to the same ntfy topic on the phone. Open SSH or a file sync path for full CSV detail.

### C. Claude Code on the host

Bounded audit paths: [claude_code_access_runbook.md](./claude_code_access_runbook.md). Claude does **not** run `--submit-paper` or order MCP tools.

---

## Docker / OrbStack (optional scheduler)

The repo ships **cron templates**, not a full compose stack. Typical operator pattern:

1. **OrbStack** or Docker Desktop on the Mac.
2. Image with Python + repo deps; mount workspace at `/app`.
3. Copy [infra/crontab](../infra/crontab) into the container crontab; ensure `PYTHONPATH=/app/src` and log path `/app/logs/ingestion_scheduler.log`.
4. SPY context store job (research): [infra/docker/crontab_spy_store](../infra/docker/crontab_spy_store).

Validate from outside the container the same way as on the host: `operator_status` against mounted `data/runs/`.

---

## Redis (optional; not in tree)

There is **no** Redis client in this repository today. State bridges are:

| Concern | File / location |
|---------|-----------------|
| Run index | `data/runs/<date>/orb_manifest.json` |
| Guard outcomes | `data/processed/risk/<run_id>_risk_audit.csv` |
| Advisory | `data/advisory/<run_id>_claude_brief.md` |
| Scheduler trace | `logs/ingestion_scheduler.log` |

If you add Redis later, treat it as an **external** job queue in front of `orb_morning_loop.py`—not a second approval path. Document the queue contract in a future implementation packet.

---

## Paper transport and reconciliation (separate packet)

Morning loop does **not** submit orders.

| Step | Command | Notes |
|------|---------|--------|
| Build / inspect payloads | `examples/build_paper_payload_candidates.py` (per packet docs) | Dry-run friendly |
| Transport dry-run | `PYTHONPATH=src python examples/submit_paper_payload_candidates.py` | Default: no broker I/O |
| Paper submit | same + `--submit-paper` | Explicit operator opt-in; `ALPACA_PAPER_*` |
| Post-submit status | `PYTHONPATH=src python examples/check_paper_order_status.py` | → `paper_order_status_audit.csv` |

Details: [alpaca-paper-bridge.md](./alpaca-paper-bridge.md), [paper-order-status-audit.md](./paper-order-status-audit.md). Capstone BCS packet: [paper_bull_call_c1_runbook.md](./paper_bull_call_c1_runbook.md).

---

## Alpaca MCP and Claude MCP diagnostics

| Tool | When |
|------|------|
| `bash scripts/diagnose_claude_mcp.sh` | Claude `/mcp` fails after `source .venv/bin/activate && claude` |
| `bash scripts/diagnose_claude_doctor_env.sh` | `/doctor` reports malformed global settings |
| `bash scripts/reconcile_claude_mcp.sh` | Wrapper → C1C diagnostic (no config copy) |

Docs: [mcp_c1c_claude_mcp_diagnostic.md](./mcp_c1c_claude_mcp_diagnostic.md), [mcp_c1d_claude_doctor_env_diagnostic.md](./mcp_c1d_claude_doctor_env_diagnostic.md), [mcp_c1a_claude_reconciliation.md](./mcp_c1a_claude_reconciliation.md) (retired copy path).

Official Alpaca MCP is **transport-only** and narrower than the full server surface ([integrations/alpaca_mcp/tool_surface.md](../integrations/alpaca_mcp/tool_surface.md)).

---

## Quick health checklist

```bash
# Repo + tests (on host)
PYTHONPATH=src python -m pytest tests -q

# Latest run exists?
PYTHONPATH=src python scripts/operator_status.py --base-dir .

# Morning flags safe?
# manifest: live_mode_enabled false, broker_mutation_occurred false

# Scheduler activity
tail -n 120 logs/ingestion_scheduler.log

# No secrets in artifacts (before external paste)
grep -R -E 'AKIA|sk-|api_key|secret|password|ALPACA_.*KEY' data/processed/ docs/audit/ data/advisory/ data/runs/ || true
```

---

## What this packet does not add

- Live trading, live Alpaca URL, or autonomous submit loops
- Redis or Tailscale binaries in the repo
- MCP config copy from Cursor into Claude (see C1C/C1D)

For capstone evidence layout, see [evidence_artifacts_guide.md](./evidence_artifacts_guide.md).
