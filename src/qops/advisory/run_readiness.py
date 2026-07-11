"""Operator readiness formatter over upstream morning_regime_status.

Not a competing taxonomy. Formats advisory JSON fields for --readiness.
Emits structured operator_next_actions with exact uv commands.
"""

from __future__ import annotations

from typing import Any

CMD_REFRESH_ADVISORY = (
    "uv run python scripts/orb_morning_loop.py --mode manual --base-dir ."
)
CMD_VIEW_READINESS = (
    "uv run python scripts/operator_status.py --base-dir . --readiness"
)
CMD_DIAGNOSE_HYDRATION = "uv run python scripts/alpaca_fetch.py --env-check"

_VAGUE_FORBIDDEN = (
    "re-run morning advisory",
    "resolve hydration",
    "try again",
    "check the data",
    "fix hydration",
)


def _field_lane(value: object) -> str:
    return str(value or "").strip()


def _private_note_status(lane: object, *, present: bool) -> str:
    if not present:
        return "MISSING"
    text = _field_lane(lane)
    if text == "PARSE_FAILED_NON_BLOCKING":
        return "NEEDS_REVIEW"
    if text == "MISSING_NON_BLOCKING":
        return "MISSING"
    return text or "MISSING"


def _action(
    *,
    action_id: str,
    reason: str,
    command: str,
    expected_output: str,
) -> dict[str, str]:
    return {
        "id": action_id,
        "reason": reason,
        "command": command,
        "expected_output": expected_output,
    }


def build_operator_next_actions(
    *,
    morning: dict[str, Any],
    private_vendor_context: dict[str, Any] | None,
    stored_morning: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    """Single source of operator guidance: structured actions with exact commands."""
    actions: list[dict[str, str]] = []
    private = private_vendor_context if isinstance(private_vendor_context, dict) else {}
    lanes = private.get("lanes") if isinstance(private.get("lanes"), dict) else {}
    presence = (
        private.get("source_presence")
        if isinstance(private.get("source_presence"), dict)
        else {}
    )
    stored = stored_morning if isinstance(stored_morning, dict) else {}

    private_accepted = bool(presence.get("macro_note") or presence.get("flow_report"))
    stored_stale = False
    if private_accepted and stored:
        for key in ("macro_context", "flow_context"):
            live = _field_lane(lanes.get(key) or morning.get(key))
            old = _field_lane(stored.get(key))
            if live and old and live != old:
                stored_stale = True
                break
        # Also stale when stored still says MISSING but live private is present/usable
        if not stored_stale:
            for key, present_key in (
                ("macro_context", "macro_note"),
                ("flow_context", "flow_report"),
            ):
                if presence.get(present_key) and _field_lane(stored.get(key)) in {
                    "",
                    "MISSING_NON_BLOCKING",
                }:
                    stored_stale = True
                    break

    if stored_stale:
        actions.append(
            _action(
                action_id="refresh_morning_advisory",
                reason=(
                    "Stored advisory artifact predates the accepted private context."
                ),
                command=CMD_REFRESH_ADVISORY,
                expected_output=(
                    "data/advisory/<run_id>_run_advisory.json regenerated; "
                    "morning_regime_status private lanes match private/parsed"
                ),
            )
        )

    hydration = _field_lane(morning.get("hydration"))
    paper_action = _field_lane(morning.get("paper_action"))
    top_reasons = morning.get("top_reasons") or []
    if not isinstance(top_reasons, list):
        top_reasons = []
    reason_blob = " ".join(str(r) for r in top_reasons).lower()
    needs_hydration = hydration in {
        "PARKED_DATA_GAP",
        "PARKED_CREDENTIAL_ERROR",
        "PARTIAL",
    } or paper_action in {"WITHHELD_DATA_GAP", "WITHHELD_CREDENTIALS"}
    if needs_hydration and (
        "quote" in reason_blob
        or "hydrat" in reason_blob
        or "credential" in reason_blob
        or "alpaca" in reason_blob
        or hydration.startswith("PARKED")
    ):
        parked = morning.get("parked_count", 0)
        actions.append(
            _action(
                action_id="diagnose_quote_hydration",
                reason=(
                    f"{parked} candidates are parked because quote hydration is incomplete "
                    f"(hydration={hydration or 'unknown'})."
                ),
                command=CMD_DIAGNOSE_HYDRATION,
                expected_output=(
                    "exit 0 when market-data credentials are present; "
                    "exit 2 on auth/credential failure"
                ),
            )
        )
        actions.append(
            _action(
                action_id="retry_hydration_via_morning_loop",
                reason=(
                    "Quote hydration runs inside the morning loop pipeline; "
                    "there is no separate hydration-only CLI."
                ),
                command=CMD_REFRESH_ADVISORY,
                expected_output=(
                    "hydration no longer reports PARKED_DATA_GAP "
                    "(or paper_action no longer WITHHELD_DATA_GAP)"
                ),
            )
        )

    if lanes.get("macro_context") == "PARSE_FAILED_NON_BLOCKING" or lanes.get(
        "flow_context"
    ) == "PARSE_FAILED_NON_BLOCKING":
        actions.append(
            _action(
                action_id="review_private_parsed_json",
                reason=(
                    "Private parsed JSON is present but marked NEEDS_REVIEW / unusable."
                ),
                command=CMD_VIEW_READINESS,
                expected_output=(
                    "private_context no longer reports NEEDS_REVIEW for the affected lane"
                ),
            )
        )

    # Always offer read-only status view as the last non-mutating check.
    if not any(a["id"] == "view_readiness" for a in actions):
        actions.append(
            _action(
                action_id="view_readiness",
                reason="Read current readiness without regenerating advisory artifacts.",
                command=CMD_VIEW_READINESS,
                expected_output="JSON readiness view printed to stdout (read-only)",
            )
        )

    return actions


def format_readiness_view(
    *,
    run_id: str,
    morning_regime_status: dict[str, Any] | None,
    macro_context_audit: dict[str, Any] | None = None,
    private_vendor_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Project upstream morning_regime_status (+ optional audit) for operator display."""
    stored_morning = (
        dict(morning_regime_status) if isinstance(morning_regime_status, dict) else {}
    )
    morning = dict(stored_morning)
    audit = macro_context_audit if isinstance(macro_context_audit, dict) else {}
    private = private_vendor_context if isinstance(private_vendor_context, dict) else {}
    lanes = private.get("lanes") if isinstance(private.get("lanes"), dict) else {}
    presence = (
        private.get("source_presence")
        if isinstance(private.get("source_presence"), dict)
        else {}
    )
    sources = private.get("sources") if isinstance(private.get("sources"), dict) else {}

    for key in (
        "macro_context",
        "flow_context",
        "skew_context",
        "vol_context",
        "index_levels_context",
    ):
        if key in lanes and str(lanes.get(key) or "") not in {"", "MISSING_NON_BLOCKING"}:
            morning[key] = lanes[key]
        elif key in lanes and presence.get(
            "macro_note" if key != "flow_context" else "flow_report"
        ):
            morning[key] = lanes[key]

    if presence.get("macro_note") and morning.get("macro_context") == "MISSING_NON_BLOCKING":
        morning["macro_context"] = lanes.get("macro_context", "PARSE_FAILED_NON_BLOCKING")
    if presence.get("flow_report") and morning.get("flow_context") == "MISSING_NON_BLOCKING":
        morning["flow_context"] = lanes.get("flow_context", "PARSE_FAILED_NON_BLOCKING")

    actions = build_operator_next_actions(
        morning=morning,
        private_vendor_context=private,
        stored_morning=stored_morning,
    )
    # Backward-compatible display strings derived from structured actions only.
    next_action_strings = [
        f"{a['id']}: {a['command']}" for a in actions if a.get("command")
    ]

    private_context = {
        "macro_note": _private_note_status(
            lanes.get("macro_context"),
            present=bool(presence.get("macro_note")),
        ),
        "flow_report": _private_note_status(
            lanes.get("flow_context"),
            present=bool(presence.get("flow_report")),
        ),
        "source_date": str(sources.get("source_date") or ""),
    }

    return {
        "run_id": run_id,
        "morning_regime_status": morning,
        "macro_context": {
            "status": morning.get("macro_context"),
            "source_type": audit.get("source_type"),
            "parse_status": audit.get("parse_status"),
            "source_file": audit.get("source_file") or sources.get("macro_note") or "",
            "warnings": audit.get("warnings", []),
            "confidence": audit.get("confidence"),
        },
        "private_context": private_context,
        "hydration": {
            "status": morning.get("hydration"),
            "parked_count": morning.get("parked_count"),
            "top_reasons": morning.get("top_reasons", []),
        },
        "quality_gate": morning.get("quality_gate"),
        "paper_action": morning.get("paper_action"),
        "selected_expression": morning.get("selected_expression"),
        "operator_next_actions": actions,
        "operator_next_action": next_action_strings,
    }
