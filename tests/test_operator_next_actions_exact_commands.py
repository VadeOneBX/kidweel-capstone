"""PRIVATE-PDF-SANITIZED-INTAKE-OPERATOR-ACTIONS-C1."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from qops.advisory.run_readiness import (
    CMD_DIAGNOSE_HYDRATION,
    CMD_REFRESH_ADVISORY,
    CMD_VIEW_READINESS,
    build_operator_next_actions,
    format_readiness_view,
)

_REPO = Path(__file__).resolve().parents[1]
_VAGUE = (
    "re-run morning advisory",
    "resolve hydration",
    "try again",
    "check the data",
    "fix hydration",
)


def test_a_exact_command_present_when_stored_advisory_stale() -> None:
    stored = {
        "macro_context": "MISSING_NON_BLOCKING",
        "flow_context": "PARSE_FAILED_NON_BLOCKING",
        "hydration": "PARKED_DATA_GAP",
        "paper_action": "WITHHELD_DATA_GAP",
        "parked_count": 43,
        "top_reasons": ["alpaca_quote_hydration_incomplete"],
    }
    private = {
        "source_presence": {"macro_note": True, "flow_report": True},
        "lanes": {
            "macro_context": "PARTIAL",
            "flow_context": "READY_LOW_CONFIDENCE",
        },
        "sources": {"source_date": "2026_07_10"},
    }
    view = format_readiness_view(
        run_id="2026-07-10-manual-150805",
        morning_regime_status=stored,
        private_vendor_context=private,
    )
    actions = view["operator_next_actions"]
    assert isinstance(actions, list) and actions
    refresh = next(a for a in actions if a["id"] == "refresh_morning_advisory")
    assert refresh["command"].startswith("uv run")
    assert refresh["command"] == CMD_REFRESH_ADVISORY
    assert refresh["reason"]
    assert refresh["expected_output"]
    assert all(a["command"].startswith("uv run") for a in actions)


def test_b_no_vague_standalone_action_phrases() -> None:
    actions = build_operator_next_actions(
        morning={
            "hydration": "PARKED_DATA_GAP",
            "paper_action": "WITHHELD_DATA_GAP",
            "parked_count": 43,
            "top_reasons": ["alpaca_quote_hydration_incomplete"],
            "macro_context": "PARTIAL",
            "flow_context": "READY_LOW_CONFIDENCE",
        },
        private_vendor_context={
            "source_presence": {"macro_note": True, "flow_report": True},
            "lanes": {
                "macro_context": "PARTIAL",
                "flow_context": "READY_LOW_CONFIDENCE",
            },
        },
        stored_morning={
            "macro_context": "MISSING_NON_BLOCKING",
            "flow_context": "PARSE_FAILED_NON_BLOCKING",
        },
    )
    blob = json.dumps(actions).lower()
    for phrase in _VAGUE:
        # Phrase may appear only inside a reason if tied to a command; forbid as sole guidance.
        assert phrase not in {a.get("id", "").lower() for a in actions}
        assert not any(
            a.get("command", "").lower() == phrase or a.get("command", "").lower() == phrase.strip()
            for a in actions
        )
    for a in actions:
        assert a["command"].startswith("uv run")
        assert " " in a["command"]


def test_c_readiness_cli_is_read_only(tmp_path: Path) -> None:
    # operator_status --readiness must not rewrite advisory JSON
    runs = tmp_path / "data" / "runs" / "2026-07-10"
    adv = tmp_path / "data" / "advisory"
    runs.mkdir(parents=True)
    adv.mkdir(parents=True)
    run_id = "2026-07-10-manual-150805"
    advisory_path = adv / f"{run_id}_run_advisory.json"
    payload = {
        "run_id": run_id,
        "morning_regime_status": {
            "macro_context": "MISSING_NON_BLOCKING",
            "flow_context": "MISSING_NON_BLOCKING",
            "hydration": "READY",
            "paper_action": "WITHHELD_QUALITY",
            "operator_next_action": "",
            "parked_count": 0,
            "top_reasons": [],
        },
        "macro_context_audit": {
            "status": "MACRO_CONTEXT_MISSING_NON_BLOCKING",
            "source_type": "missing",
            "parse_status": "MISSING_OPTIONAL_CONTEXT",
            "warnings": [],
            "confidence": "LOW",
        },
    }
    advisory_path.write_text(json.dumps(payload), encoding="utf-8")
    before = advisory_path.read_text(encoding="utf-8")
    # minimal manifest
    from qops.runtime.orb_manifest import OrbRunManifest, write_manifest
    from datetime import datetime
    from zoneinfo import ZoneInfo

    manifest = OrbRunManifest(
        run_id=run_id,
        run_date="2026-07-10",
        run_ts=datetime(2026, 7, 10, 15, 8, 5, tzinfo=ZoneInfo("America/New_York")),
        mode="manual",
        status="ADVISORY_COMPLETE",
    )
    write_manifest(tmp_path, manifest)
    env = {**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONPATH": str(_REPO / "src")}
    proc = subprocess.run(
        [
            sys.executable,
            str(_REPO / "scripts" / "operator_status.py"),
            "--base-dir",
            str(tmp_path),
            "--date",
            "2026-07-10",
            "--readiness",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    after = advisory_path.read_text(encoding="utf-8")
    assert after == before
    out = json.loads(proc.stdout)
    assert "operator_next_actions" in out
    assert all(a["command"].startswith("uv run") for a in out["operator_next_actions"])


def test_d_docs_state_sanitized_private_raw_boundary() -> None:
    docs = (_REPO / "docs" / "operator_commands.md").read_text(encoding="utf-8").lower()
    assert "sanitized working pdfs only" in docs or "sanitized working pdfs" in docs
    assert "outside the repository" in docs
    assert "raw input to the parser" in docs


def test_e_no_false_sanitization_claim_in_docs() -> None:
    docs = (_REPO / "docs" / "operator_commands.md").read_text(encoding="utf-8").lower()
    for claim in (
        "parser strips images",
        "automatically redacts",
        "ocr pipeline",
        "ocr fallback",
        "vision extraction",
    ):
        assert claim not in docs


def test_hydration_actions_use_exact_commands() -> None:
    actions = build_operator_next_actions(
        morning={
            "hydration": "PARKED_DATA_GAP",
            "paper_action": "WITHHELD_DATA_GAP",
            "parked_count": 43,
            "top_reasons": ["alpaca_quote_hydration_incomplete"],
        },
        private_vendor_context={
            "source_presence": {"macro_note": True, "flow_report": True},
            "lanes": {"macro_context": "PARTIAL", "flow_context": "READY_LOW_CONFIDENCE"},
        },
        stored_morning={"macro_context": "PARTIAL", "flow_context": "READY_LOW_CONFIDENCE"},
    )
    by_id = {a["id"]: a for a in actions}
    assert by_id["diagnose_quote_hydration"]["command"] == CMD_DIAGNOSE_HYDRATION
    assert by_id["retry_hydration_via_morning_loop"]["command"] == CMD_REFRESH_ADVISORY
    assert by_id["view_readiness"]["command"] == CMD_VIEW_READINESS
