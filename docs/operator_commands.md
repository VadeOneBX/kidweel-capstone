# Kidweel Operator Commands

Remote scheduling, Tailscale/SSH, push notifications, Docker cron templates, and paper reconcile: [connectors_c1_runbook.md](./connectors_c1_runbook.md).

**Tests by morning-loop phase (uv + Docker):** [operator_test_commands_morning_loop.md](./operator_test_commands_morning_loop.md).

**Surfaces:** Commands below run on the **operator runtime boundary** (host shell or SSH via Tailscale)—not in Claude.ai, Claude mobile, or Cursor mobile chat. Those surfaces review artifacts or apply scoped repo edits; they do not approve, submit, or bypass gates. Taxonomy: [CLAUDE.md](../CLAUDE.md#surface-taxonomy-authority-matters).

## Host setup (uv + optional Docker)

One-time from repo root:

```bash
uv sync
cp .env.example .env   # once; edit locally — never commit
```

With OrbStack/Docker running Redis and QOPS API (see [mobile_infra_runbook.md](./mobile_infra_runbook.md)):

```bash
docker compose up --build
```

Host `.env` should keep `REDIS_URL=redis://localhost:6379/0` so `uv run` scripts and cron tests hit the published Redis port while containers use `redis://redis:6379/0` internally.

Runtime checks (API up):

```bash
curl -s http://localhost:8000/health | jq .
curl -s http://localhost:8000/status | jq .
uv run python scripts/cron_trigger.py --source manual --dry-run
```

## Check manual upload folder

```bash
ls -lah data/spotgamma/raw/$(date +%F)
```

## Check transient inbox

```bash
ls -lah data/spotgamma/inbox
```

## Morning Regime workbook (daily)

The upgraded Morning Regime is now the standard Morning Regime. Operators stage it as `morning_regime.xlsx`; the system detects upgraded tabs by sheet presence (`morning_regime`, `unusual_options_positions`, `stat_sig_positions`, `flow_candidates`). The `_UPGRADE` filename suffix is for tests and backward compatibility only—not a separate live intake path.

```bash
# Stage the daily Morning Regime workbook
cp /path/to/raw/morning_regime.xlsx data/spotgamma/inbox/morning_regime.xlsx

# Run morning wake / staging
uv run python scripts/daily_ingestion_wake.py --mode manual --base-dir .

# Run morning loop through advisory (pipeline, risk guard, run advisory JSON)
uv run python scripts/orb_morning_loop.py --mode manual --base-dir .

# Check Morning Regime flow audit (structured tabs; no OCR)
cat logs/morning_regime_latest.json
```

`orb_morning_loop.py` runs ingestion wake again at loop start; that is expected. Fast advisory and the audit file are produced when the staged workbook includes the upgraded sheets. Paper submission remains gated by existing risk and macro gates.

## Run wake only

```bash
uv run python scripts/daily_ingestion_wake.py --mode manual --base-dir .
```

## Run full morning loop

```bash
uv run python scripts/orb_morning_loop.py --mode manual --base-dir .
```

## Run full loop without notification

```bash
uv run python scripts/orb_morning_loop.py --mode manual --base-dir . --no-notify
```

## Check latest manifest

```bash
uv run python scripts/operator_status.py --base-dir .
```

## View advisory brief (deterministic artifact)

Morning brief from `qops.advisory.claude_brief`—not claude-advisor skill output. Review on host or via Tailscale; Claude.ai / Claude mobile are visibility surfaces only.

```bash
cat data/advisory/latest_claude_brief.md
grep -A 3 "vote:" data/advisory/latest_claude_brief.md
```

## Post-ORB idea artifacts (Tier 3)

```bash
find data/runs -name "*_ideas.json" | sort | tail -n 5
uv run python scripts/operator_status.py --base-dir . --ideas-summary
```

## View latest notification payload

```bash
cat data/notifications/latest_notification.json
```

## Tail scheduler log

```bash
tail -n 120 logs/ingestion_scheduler.log
```

## Confirm recent run artifacts

```bash
find data/runs -type f | sort | tail -n 10
find data/processed -type f | sort | tail -n 20
```

## Emergency halt

```bash
touch data/.execution_halt
```

## Resume after halt

```bash
rm data/.execution_halt
```
