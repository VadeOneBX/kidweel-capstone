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

    context_artifact: str | None = None
    candidates_artifact: str | None = None
    risk_audit_artifact: str | None = None
    advisory_artifact: str | None = None
    notification_artifact: str | None = None

    live_mode_enabled: bool = False
    broker_mutation_occurred: bool = False

    errors: list[str] = Field(default_factory=list)


def manifest_path(base_dir: Path, run_date: str) -> Path:
    return base_dir / "data" / "runs" / run_date / "orb_manifest.json"


def write_manifest(base_dir: Path, manifest: OrbRunManifest) -> Path:
    path = manifest_path(base_dir, manifest.run_date)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return path


def read_manifest(base_dir: Path, run_date: str) -> OrbRunManifest:
    path = manifest_path(base_dir, run_date)
    return OrbRunManifest.model_validate_json(path.read_text(encoding="utf-8"))
