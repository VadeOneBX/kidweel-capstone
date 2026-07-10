"""Operator readiness formatter over upstream morning_regime_status.

Not a competing taxonomy. Formats advisory JSON fields for --readiness.
"""

from __future__ import annotations

from typing import Any


def format_readiness_view(
    *,
    run_id: str,
    morning_regime_status: dict[str, Any] | None,
    macro_context_audit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Project upstream morning_regime_status (+ optional audit) for operator display."""
    morning = morning_regime_status if isinstance(morning_regime_status, dict) else {}
    audit = macro_context_audit if isinstance(macro_context_audit, dict) else {}
    next_action = morning.get("operator_next_action", "")
    if isinstance(next_action, str):
        next_actions: list[str] = [next_action] if next_action else []
    elif isinstance(next_action, list):
        next_actions = [str(x) for x in next_action]
    else:
        next_actions = []

    return {
        "run_id": run_id,
        "morning_regime_status": morning,
        "macro_context": {
            "status": morning.get("macro_context"),
            "source_type": audit.get("source_type"),
            "parse_status": audit.get("parse_status"),
            "source_file": audit.get("source_file"),
            "warnings": audit.get("warnings", []),
            "confidence": audit.get("confidence"),
        },
        "hydration": {
            "status": morning.get("hydration"),
        },
        "quality_gate": morning.get("quality_gate"),
        "paper_action": morning.get("paper_action"),
        "selected_expression": morning.get("selected_expression"),
        "operator_next_action": next_actions,
    }
