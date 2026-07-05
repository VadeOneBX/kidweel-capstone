# Mobile Infra Runbook

## Purpose

This layer gives Kidweel a local-first **runtime surface** for operator visibility—not an implementation or advisory authority path.

It supports:

- local health checks
- Redis-backed status handoff
- cron-triggered wake messages
- future mobile notifications
- future **Cursor mobile** packs that need a stable runtime surface

It does not approve trades, submit orders, or replace the **operator** decision-maker.

**Surfaces:** QOPS API and cron paths here are the **runtime command boundary**. **Claude mobile** is review-only unless routed through a future allowlisted operator boundary. **Cursor mobile** scopes repo edits and diff review—it does not run morning loop submit paths or bypass gates. Taxonomy: [CLAUDE.md](../CLAUDE.md#surface-taxonomy-authority-matters).

## Local OrbStack Run

```bash
cp .env.example .env
docker compose up --build
```

Health check:

```bash
curl http://localhost:8000/health
```

Expected:

```json
{
  "ok": true,
  "service": "qops-api",
  "paper_only": true,
  "redis_ok": true
}
```

Trigger dry-run:

```bash
curl -X POST http://localhost:8000/trigger \
  -H "Content-Type: application/json" \
  -d '{"name":"orb_wake","dry_run":true,"source":"mobile-test"}'
```

Inspect bus:

```bash
curl http://localhost:8000/bus/qops.trigger
```

## Local uv Path

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
PYTHONPATH=src uvicorn qops.runtime.app:app --reload
```

Cron schedules in `docker/crontab` use the container’s default timezone (UTC unless you configure `TZ`). For macOS-only cron outside Docker, run `scripts/cron_trigger.py` manually or wire your own local scheduler.

## Cron Test

```bash
PYTHONPATH=src python scripts/cron_trigger.py --source manual --dry-run
cat logs/cron_trigger_latest.json
```

## Acceptance

- API starts locally.
- Redis starts locally.
- `/health` returns `paper_only: true`.
- Cron trigger writes `logs/cron_trigger_latest.json`.
- Redis bus stores recent messages.
- No live trading endpoint is introduced.
