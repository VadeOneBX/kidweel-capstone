# OPENAI-AGENTS-HITL-PAPER-TRANSPORT-C1

Human-in-the-loop approval boundary for Alpaca **paper** transport only.

## Purpose

Convert manual review into a **resumable approval state** before any paper order submission:

`candidate built → gates pass → paper transport requested → run interrupts → operator approves/rejects → audit written`

This packet does **not** enable live trading, loosen gates, or auto-submit on approve.

## States

| Status | Meaning |
|--------|---------|
| `APPROVAL_REQUIRED` | Default for transport-ready candidates |
| `APPROVED_BY_OPERATOR` | Operator approved; paper submit may proceed |
| `REJECTED_BY_OPERATOR` | Operator rejected; submit blocked |
| `WATCH_PENDING_REVIEW` | WATCH candidate; unresolved without operator decision |
| `CLEAN_REJECT` | Failed existing repo gates |
| `LIVE_ENV_FORBIDDEN` | `ALPACA_LIVE_TRADE` live flag detected |

Default action without operator approval: **`DO_NOT_SUBMIT`**.

## Artifacts

- Pending state: `logs/hitl/pending/<candidate_id>.json`
- Audit JSON: `logs/hitl/YYYY-MM-DD_HHMMSS_<candidate_id>_hitl_approval.json`

Audit records include `packet: OPENAI-AGENTS-HITL-PAPER-TRANSPORT-C1`, `paper_only: true`, and `live_env_forbidden: true`.

## CLI

```bash
python scripts/hitl_review.py --list-pending
python scripts/hitl_review.py --candidate-id <id> --decision approve --reason "operator approved paper test"
python scripts/hitl_review.py --candidate-id <id> --decision reject --reason "RR/PMP not acceptable"
```

Approve/reject **only updates approval state**; it does not place broker orders.

## Integration

`run_paper_payload_transport` and `submit_alpaca_paper_mleg_order` consult `qops.execution.hitl_paper_transport` before network I/O when `submit_paper` is true.

OpenAI Agents SDK HITL is optional; the repo-local serialize / pending artifact / resume path is canonical.

## Invariants

- `paper_only` is always true on approval items.
- `live_env_forbidden` is always true on approval items.
- Live env (`ALPACA_LIVE_TRADE=true|1|yes|on`) returns `LIVE_ENV_FORBIDDEN` and blocks transport.
