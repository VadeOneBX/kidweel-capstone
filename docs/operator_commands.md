# Kidweel Operator Commands

Remote scheduling, Tailscale/SSH, push notifications, Docker cron templates, and paper reconcile: [connectors_c1_runbook.md](./connectors_c1_runbook.md).

## Check manual upload folder

```bash
ls -lah data/spotgamma/raw/$(date +%F)
```

## Check transient inbox

```bash
ls -lah data/spotgamma/inbox
```

## Run wake only

```bash
PYTHONPATH=src python scripts/daily_ingestion_wake.py --mode manual --base-dir .
```

## Run full morning loop

```bash
PYTHONPATH=src python scripts/orb_morning_loop.py --mode manual --base-dir .
```

## Run full loop without notification

```bash
PYTHONPATH=src python scripts/orb_morning_loop.py --mode manual --base-dir . --no-notify
```

## Check latest manifest

```bash
PYTHONPATH=src python scripts/operator_status.py --base-dir .
```

## View Claude advisory

```bash
cat data/advisory/latest_claude_brief.md
grep -A 3 "vote:" data/advisory/latest_claude_brief.md
```

## Post-ORB idea artifacts (Tier 3)

```bash
find data/runs -name "*_ideas.json" | sort | tail -n 5
PYTHONPATH=src python scripts/operator_status.py --base-dir . --ideas-summary
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
