from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

RunMode = Literal["orb-watchdog", "orb-final", "manual"]

RunStatus = Literal[
    "STARTED",
    "NO_FILES",
    "FILES_STAGED",
    "FILES_REJECTED",
    "INGESTION_COMPLETE",
    "PIPELINE_COMPLETE",
    "RISK_GUARD_COMPLETE",
    "ADVISORY_COMPLETE",
    "NOTIFICATION_COMPLETE",
    "FAILED",
]


class OrbRunManifest(BaseModel):
    run_id: str
    run_date: str
    run_ts: datetime
    mode: RunMode
    status: RunStatus = "STARTED"

    files_found: int = 0
    files_staged: int = 0
    files_rejected: int = 0

    staged_files: list[str] = Field(default_factory=list)
    rejected_files: list[str] = Field(default_factory=list)
    rejection_reasons: dict[str, str] = Field(default_factory=dict)
    source_to_staged: dict[str, str] = Field(default_factory=dict)

    context_artifact: str | None = None
    candidates_artifact: str | None = None
    risk_audit_artifact: str | None = None
    advisory_artifact: str | None = None
    notification_artifact: str | None = None

    live_mode_enabled: bool = False
    broker_mutation_occurred: bool = False
    notification_sent: bool = False

    errors: list[str] = Field(default_factory=list)


def manifest_path(base_dir: Path, run_date: str) -> Path:
    """Latest manifest for a calendar run date (overwritten each wake on that date)."""
    return base_dir / "data" / "runs" / run_date / "orb_manifest.json"


def immutable_manifest_path(base_dir: Path, run_date: str, run_id: str) -> Path:
    """Immutable manifest snapshot for one run_id."""
    return base_dir / "data" / "runs" / run_date / f"{run_id}_orb_manifest.json"


def append_scheduler_log(base_dir: Path, message: str) -> None:
    log_path = base_dir / "logs" / "ingestion_scheduler.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(message.rstrip() + "\n")


def write_manifest(base_dir: Path, manifest: OrbRunManifest) -> Path:
    payload = manifest.model_dump_json(indent=2)
    latest = manifest_path(base_dir, manifest.run_date)
    immutable = immutable_manifest_path(base_dir, manifest.run_date, manifest.run_id)
    latest.parent.mkdir(parents=True, exist_ok=True)
    latest.write_text(payload, encoding="utf-8")
    immutable.write_text(payload, encoding="utf-8")
    return latest


def read_manifest(base_dir: Path, run_date: str) -> OrbRunManifest:
    path = manifest_path(base_dir, run_date)
    return OrbRunManifest.model_validate_json(path.read_text(encoding="utf-8"))


def read_manifest_by_run_id(base_dir: Path, run_date: str, run_id: str) -> OrbRunManifest:
    path = immutable_manifest_path(base_dir, run_date, run_id)
    return OrbRunManifest.model_validate_json(path.read_text(encoding="utf-8"))
