"""Tests for scripts/operator_status.py operator CLI."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO_ROOT / "scripts" / "operator_status.py"
_SUBPROCESS_ENV = {**os.environ, "PYTHONPATH": str(_REPO_ROOT / "src")}


def _run_operator_status(*args: str, base_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), "--base-dir", str(base_dir), *args],
        capture_output=True,
        text=True,
        check=False,
        env=_SUBPROCESS_ENV,
    )


def _idea(idea_type: str, symbol: str) -> dict:
    return {
        "idea_type": idea_type,
        "symbol": symbol,
        "source": "data/processed/mock_sg_context.csv",
        "data_basis": {
            "directional_bias": "bullish",
            "source_panel": "context_artifact",
        },
        "reason": "test",
    }


def _write_ideas_artifact(
    base_dir: Path,
    run_date: str,
    run_id: str,
    agent_id: str,
    idea_source: str,
    ideas: list[dict],
) -> Path:
    run_dir = base_dir / "data" / "runs" / run_date
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / f"{run_id}_{agent_id}_ideas.json"
    path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "agent_id": agent_id,
                "idea_source": idea_source,
                "ideas": ideas,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_operator_status_accepts_base_dir(tmp_path: Path) -> None:
    proc = _run_operator_status(base_dir=tmp_path)
    assert proc.returncode == 1
    assert "NO_MANIFEST_FOUND" in proc.stdout


def test_operator_status_accepts_base_dir_and_ideas_summary(tmp_path: Path) -> None:
    _write_ideas_artifact(
        tmp_path,
        "2026-07-06",
        "orb-final-120000",
        "squeeze-candidates",
        "squeeze",
        [
            _idea("PROPOSE", "AAPL"),
            _idea("WATCH", "MSFT"),
            _idea("PASS", "SOFI"),
        ],
    )

    proc = _run_operator_status("--ideas-summary", base_dir=tmp_path)
    assert proc.returncode == 0
    assert "run_date=2026-07-06" in proc.stdout
    assert "run_id=orb-final-120000" in proc.stdout
    assert "PROPOSE=1" in proc.stdout
    assert "WATCH=1" in proc.stdout
    assert "PASS=1" in proc.stdout


def test_operator_status_ideas_summary_degrades_when_no_ideas_exist(tmp_path: Path) -> None:
    proc = _run_operator_status("--ideas-summary", base_dir=tmp_path)
    assert proc.returncode == 0
    assert proc.stdout.strip() == "NO_IDEA_ARTIFACTS_FOUND"


def test_operator_status_readiness_reads_run_advisory(tmp_path: Path) -> None:
    run_id = "2026-07-08-manual-093942"
    advisory_dir = tmp_path / "data/advisory"
    advisory_dir.mkdir(parents=True)
    (advisory_dir / f"{run_id}_run_advisory.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "run_readiness": {
                    "woke": True,
                    "macro": {
                        "status": "MACRO_CONTEXT_READY_LOW_CONFIDENCE",
                        "source": "xlsx_founders_note",
                        "summary": "low confidence",
                        "blocks_run": False,
                    },
                    "hydration": {
                        "status": "PARKED_CREDENTIAL_ERROR",
                        "reason": "credential_error:no_credential_pair",
                        "parked_count": 49,
                    },
                    "selection": {
                        "status": "PARKED",
                        "reason": "credential_error:no_credential_pair",
                        "parked_count": 49,
                    },
                },
                "morning_regime_status": {
                    "quality_gate": "NO_ACTION_QUALITY",
                    "paper_action": "WITHHELD_CREDENTIALS",
                },
            }
        ),
        encoding="utf-8",
    )

    proc = _run_operator_status(
        "--readiness",
        "--run-id",
        run_id,
        "--date",
        "2026-07-08",
        base_dir=tmp_path,
    )
    assert proc.returncode == 0
    assert "MACRO_CONTEXT_READY_LOW_CONFIDENCE" in proc.stdout
    assert "PARKED_CREDENTIAL_ERROR" in proc.stdout
    assert "blocked" not in proc.stdout.lower()


def test_operator_status_ideas_summary_is_read_only(tmp_path: Path) -> None:
    path = _write_ideas_artifact(
        tmp_path,
        "2026-07-06",
        "orb-final-120000",
        "volatility-risk-premium",
        "vrp",
        [
            _idea("PROPOSE", "AAPL"),
            _idea("PROPOSE", "MSFT"),
            _idea("PASS", "SOFI"),
        ],
    )
    before = path.read_text(encoding="utf-8")

    proc = _run_operator_status("--ideas-summary", base_dir=tmp_path)
    assert proc.returncode == 0
    assert path.read_text(encoding="utf-8") == before
    assert "PROPOSE=2" in proc.stdout
