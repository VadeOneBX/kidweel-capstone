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
# Stage the daily Morning Regime workbook (repo-relative paths from repo root)
cp data/spotgamma/raw/$(date +%F)/morning_regime.xlsx data/spotgamma/inbox/morning_regime.xlsx

# Run morning wake / staging
uv run python scripts/daily_ingestion_wake.py --mode manual --base-dir .

# Run morning loop through advisory (pipeline, risk guard, run advisory JSON)
uv run python scripts/orb_morning_loop.py --mode manual --base-dir .

# Check Morning Regime flow audit (structured tabs; no OCR)
cat logs/morning_regime_latest.json
```

`orb_morning_loop.py` runs ingestion wake again at loop start; that is expected. Fast advisory and the audit file are produced when the staged workbook includes the upgraded sheets. Paper submission remains gated by existing risk and execution gates—not by AM-note parse quality alone.

### Macro context degrade-not-block

Priority (highest wins):

1. `data/advisory/{run_id}_macro_context_override.json` (manual emergency override; audit-loud)
2. Structured AM-note sidecar `.json` / `.csv` under staging (preferred)
3. Workbook prose note inside staged `morning_regime.xlsx` (low-confidence fallback)
4. Degraded non-blocking status (`MISSING_NON_BLOCKING` / `UNPARSED_NON_BLOCKING` on `morning_regime_status.macro_context`)

Clarify:

- Missing or unparsed AM-note / workbook prose **does not block** the morning loop; it reduces confidence and emits warnings.
- Alpaca credential errors park **hydration** only; they are not macro-context failures.
- Authoritative operator lanes live on `morning_regime_status` (upstream readiness spine).

```bash
uv run python scripts/operator_status.py --base-dir . --readiness
```

### No-action outcomes

- Do nothing is a first-class output.
- No paper action can mean quality gates worked as intended.
- Morning Regime should complete with artifacts even when no expression is selected.
- Reserve "blocked" for true missing required inputs or safety violations.
- `paper_approval_allowed=true` means paper consideration is not safety-blocked; it is **not** trade selection or submit approval.

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

## Check readiness lanes (morning_regime_status)

`--run-id` takes the **full run id string** from the morning loop / manifest
(e.g. `2026-07-13-manual-164239`), not only the numeric time suffix or date digits.

```bash
uv run python scripts/operator_status.py --base-dir . --readiness
uv run python scripts/operator_status.py --base-dir . --run-id 2026-07-13-manual-164239 --readiness
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

## Private vendor PDF ingest

Private vendor PDFs may be used as local advisory inputs.

### Private PDF intake boundary

`private/raw/` accepts sanitized working PDFs only.

Before placing a PDF under `private/raw/`, remove material that is not required for the intended parser lane, including:

- images and screenshots
- advertisements, appendices, and unrelated sections
- personal or account-identifying information

Keep only the text and tables needed for the selected lane:

- `macro_note`
- `flow_report`

The original source PDF must remain outside the repository tree.

`private/raw/` means raw input to the parser. It does not mean an untouched source document.

### Private PDF preparation workflow

```text
Original source:
outside repo

Sanitized derivative:
private/raw/macro_note_YYYY_MM_DD.pdf
private/raw/flow_report_YYYY_MM_DD.pdf

Parser outputs:
private/text/{stem}.txt
private/parsed/{stem}.json
```

Operator preflight (placement check only; does not sanitize):

```bash
find private/raw -maxdepth 1 -type f -name '*.pdf' -print
git check-ignore -v private/raw/*.pdf
```

### Private PDF operator commands

| Action | Exact command |
|--------|----------------|
| Regenerate morning advisory artifact | `uv run python scripts/orb_morning_loop.py --mode manual --base-dir .` |
| View readiness (read-only) | `uv run python scripts/operator_status.py --base-dir . --readiness` |
| Diagnose Alpaca market-data credentials | `uv run python scripts/alpaca_fetch.py --env-check` |

Hydration retry is not a separate CLI. Quote hydration runs inside the morning loop pipeline; after credentials/data are fixed, regenerate with `orb_morning_loop.py`.

Rules:

- Store raw PDFs only under `private/raw/`.
- Store extracted text only under `private/text/`.
- Store parsed JSON only under `private/parsed/`.
- Do not commit raw PDFs, extracted text, or parsed private JSON.
- Morning Regime consumes sanitized derived context only.
- Public docs, README, briefs, and PR summaries must not include raw vendor prose, tables, report names, or source-specific field inventories.

Sanitized lanes:

- macro_context
- flow_context
- skew_context
- vol_context
- index_levels_context

Allowed lane states:

- READY
- READY_LOW_CONFIDENCE
- PARTIAL
- MISSING_NON_BLOCKING
- PARSE_FAILED_NON_BLOCKING

```bash
uv run python scripts/parse_private_vendor_pdf.py \
  --kind macro_note \
  --pdf private/raw/macro_note_2026_07_09.pdf \
  --out private/parsed/macro_note_2026_07_09.json

uv run python scripts/parse_private_vendor_pdf.py \
  --kind flow_report \
  --pdf private/raw/flow_report_2026_07_09.pdf \
  --out private/parsed/flow_report_2026_07_09.json
```

Expected success line:

```bash
Wrote private/parsed/<stem>.json
```

### Private PDF parse exit reasons

Private PDF parsing writes private artifacts only under `private/`.

| Exit | Meaning | Operator action |
|------|---------|-----------------|
| `0` | Parse succeeded. Parsed JSON was written to `private/parsed/`. | Continue to readiness check. |
| `2` | `NEEDS_REVIEW`. The parser wrote JSON, but the source had no extractable text or could not be confidently parsed. | Review the PDF/text manually. Do not treat it as a clean parse. |
| other | Parse failed unexpectedly. | Check stderr, file path, kind, and private directory setup. |

There is no dedicated parse audit file; use stdout/stderr and the written JSON.

### OCR posture

No OCR is performed.

If a PDF has no extractable text, the parser returns `NEEDS_REVIEW` and writes review-marked JSON to the requested output path.

Operator action:
use a text-based PDF when available, or manually review the source outside the repo.

## Emergency halt

```bash
touch data/.execution_halt
```

## Resume after halt

```bash
rm data/.execution_halt
```
