from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from qops.ingest.file_contracts import evaluate_ingestion_file
from qops.runtime.orb_manifest import OrbRunManifest, RunMode, write_manifest

_IGNORED_INTAKE_FILENAMES = frozenset({".gitkeep", ".DS_Store"})


@dataclass(frozen=True, slots=True)
class _IntakeFile:
    path: Path
    from_raw_session: bool


def bootstrap_runtime_dirs(base_dir: Path) -> None:
    dirs = [
        "data/spotgamma/inbox",
        "data/spotgamma/staging",
        "data/spotgamma/processed",
        "data/spotgamma/rejected",
        "data/processed/context",
        "data/processed/candidates",
        "data/processed/risk",
        "data/advisory",
        "data/notifications",
        "data/runs",
        "logs",
    ]

    for rel in dirs:
        (base_dir / rel).mkdir(parents=True, exist_ok=True)


def _collect_intake_files(base_dir: Path, run_date: str) -> list[_IntakeFile]:
    raw_date_dir = base_dir / "data/spotgamma/raw" / run_date
    inbox_dir = base_dir / "data/spotgamma/inbox"
    source_dirs: list[tuple[Path, bool]] = [
        (raw_date_dir, True),
        (inbox_dir, False),
    ]

    found: list[_IntakeFile] = []
    claimed_normalized: set[str] = set()
    for source_dir, from_raw in source_dirs:
        if not source_dir.is_dir():
            continue
        for path in sorted(source_dir.iterdir()):
            if not path.is_file() or path.name in _IGNORED_INTAKE_FILENAMES:
                continue
            result = evaluate_ingestion_file(path, run_date=run_date)
            if result.accepted and result.normalized_name:
                if result.normalized_name in claimed_normalized:
                    continue
                claimed_normalized.add(result.normalized_name)
            found.append(_IntakeFile(path=path, from_raw_session=from_raw))
    return found


def run_ingestion_wake(
    base_dir: Path,
    mode: RunMode,
    dry_run: bool = False,
) -> OrbRunManifest:
    bootstrap_runtime_dirs(base_dir)

    now_et = datetime.now(ZoneInfo("America/New_York"))
    run_date = now_et.strftime("%Y-%m-%d")
    run_id = f"{run_date}-{mode}-{now_et.strftime('%H%M%S')}"

    staging_dir = base_dir / "data/spotgamma/staging"
    rejected_dir = base_dir / "data/spotgamma/rejected"

    manifest = OrbRunManifest(
        run_id=run_id,
        run_date=run_date,
        run_ts=now_et,
        mode=mode,
    )

    intake_files = _collect_intake_files(base_dir, run_date)
    manifest.files_found = len(intake_files)

    if not intake_files:
        manifest.status = "NO_FILES"
        write_manifest(base_dir, manifest)
        return manifest

    for item in intake_files:
        path = item.path
        source_key = str(path.resolve())
        result = evaluate_ingestion_file(path, run_date=run_date)

        if not result.accepted:
            manifest.files_rejected += 1
            manifest.rejection_reasons[source_key] = result.reason
            if not item.from_raw_session:
                target = rejected_dir / path.name
                manifest.rejected_files.append(str(target))
                if not dry_run:
                    shutil.move(str(path), str(target))
            continue

        target = staging_dir / result.normalized_name
        manifest.files_staged += 1
        staged_key = str(target.resolve())
        manifest.staged_files.append(staged_key)
        manifest.source_to_staged[source_key] = staged_key

        if not dry_run:
            if item.from_raw_session:
                shutil.copy2(str(path), str(target))
            else:
                shutil.move(str(path), str(target))

    if manifest.files_staged > 0:
        manifest.status = "FILES_STAGED"
    else:
        manifest.status = "FILES_REJECTED"

    write_manifest(base_dir, manifest)
    return manifest
