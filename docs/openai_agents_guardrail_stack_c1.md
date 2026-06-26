# OPENAI-AGENTS-GUARDRAIL-STACK-C1

Blocking guardrails run **before** HITL and paper transport.

## Order

1. Paper environment (`check_paper_environment`)
2. Required fields (`check_required_fields`)
3. Structure (`check_structure_allowed`) — repo policy: four defined-risk spreads from `docs/system-identity.md`
4. Leg payload (`check_leg_payload`)
5. Economics (`check_economics`)
6. WATCH boundary (`check_watch_boundary`)

## Semantics

- Guardrails are **blocking by default**.
- Invalid candidates **do not** reach `load_or_create_approval` except `WATCH_PENDING_REVIEW` (operator review artifact only; no submit).
- Valid candidates (`PASS`) proceed to the HITL approval boundary.

## Audit

Blocking outcomes write:

`logs/guardrails/YYYY-MM-DD_HHMMSS_<candidate_id>_<reason_code>.json`

## OpenAI Agents

Optional SDK wrappers may mirror these checks; repo-local `evaluate_guardrails()` is canonical.
