from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from qops.ingest.file_contracts import evaluate_ingestion_file
from qops.runtime.orb_manifest import OrbRunManifest, RunMode, write_manifest


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


def run_ingestion_wake(
    base_dir: Path,
    mode: RunMode,
    dry_run: bool = False,
) -> OrbRunManifest:
    bootstrap_runtime_dirs(base_dir)

    now_et = datetime.now(ZoneInfo("America/New_York"))
    run_date = now_et.strftime("%Y-%m-%d")
    run_id = f"{run_date}-{mode}-{now_et.strftime('%H%M%S')}"

    inbox_dir = base_dir / "data/spotgamma/inbox"
    staging_dir = base_dir / "data/spotgamma/staging"
    rejected_dir = base_dir / "data/spotgamma/rejected"

    manifest = OrbRunManifest(
        run_id=run_id,
        run_date=run_date,
        run_ts=now_et,
        mode=mode,
    )

    files = sorted([p for p in inbox_dir.iterdir() if p.is_file() and p.name != ".gitkeep"])
    manifest.files_found = len(files)

    if not files:
        manifest.status = "NO_FILES"
        write_manifest(base_dir, manifest)
        return manifest

    for path in files:
        result = evaluate_ingestion_file(path, run_date=run_date)

        if not result.accepted:
            target = rejected_dir / path.name
            manifest.files_rejected += 1
            manifest.rejected_files.append(str(target))
            manifest.rejection_reasons[path.name] = result.reason

            if not dry_run:
                shutil.move(str(path), str(target))

            continue

        target = staging_dir / result.normalized_name
        manifest.files_staged += 1
        manifest.staged_files.append(str(target))

        if not dry_run:
            shutil.move(str(path), str(target))

    if manifest.files_staged > 0:
        manifest.status = "FILES_STAGED"
    else:
        manifest.status = "FILES_REJECTED"

    write_manifest(base_dir, manifest)
    return manifest
