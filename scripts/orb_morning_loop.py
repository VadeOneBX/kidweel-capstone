from __future__ import annotations

import argparse
from pathlib import Path

from qops.advisory.claude_brief import generate_claude_brief
from qops.ingest.ingestion_wake import run_ingestion_wake
from qops.notify.mobile_notify import send_mobile_notification
from qops.pipeline.daily_pipeline import run_daily_pipeline
from qops.risk.guard_runner import run_risk_guard
from qops.runtime.orb_manifest import write_manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["orb-watchdog", "orb-final", "manual"],
        default="manual",
    )
    parser.add_argument("--base-dir", default=".")
    parser.add_argument("--no-notify", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--live", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.live:
        raise RuntimeError("LIVE_MODE_FORBIDDEN")

    base_dir = Path(args.base_dir).resolve()

    manifest = run_ingestion_wake(
        base_dir=base_dir,
        mode=args.mode,
        dry_run=args.dry_run,
    )

    if manifest.status in {"NO_FILES", "FILES_REJECTED"}:
        write_manifest(base_dir, manifest)
        print(manifest.model_dump_json(indent=2))
        return 0

    try:
        pipeline_result = run_daily_pipeline(
            base_dir=base_dir,
            run_id=manifest.run_id,
            staged_files=manifest.staged_files,
            dry_run=True,
        )

        manifest.context_artifact = pipeline_result.context_artifact
        manifest.candidates_artifact = pipeline_result.candidates_artifact
        manifest.status = "PIPELINE_COMPLETE"
        write_manifest(base_dir, manifest)

        risk_result = run_risk_guard(
            base_dir=base_dir,
            run_id=manifest.run_id,
            candidates_artifact=manifest.candidates_artifact,
            paper_only=True,
        )

        manifest.risk_audit_artifact = risk_result.risk_audit_artifact
        manifest.status = "RISK_GUARD_COMPLETE"
        write_manifest(base_dir, manifest)

        advisory_result = generate_claude_brief(
            base_dir=base_dir,
            manifest=manifest,
        )

        manifest.advisory_artifact = advisory_result.advisory_artifact
        manifest.status = "ADVISORY_COMPLETE"
        write_manifest(base_dir, manifest)

        if not args.no_notify:
            notification_result = send_mobile_notification(
                base_dir=base_dir,
                manifest=manifest,
                advisory_artifact=manifest.advisory_artifact,
            )

            manifest.notification_artifact = notification_result.notification_artifact
            manifest.status = "NOTIFICATION_COMPLETE"
            write_manifest(base_dir, manifest)

    except Exception as exc:
        manifest.status = "FAILED"
        manifest.errors.append(repr(exc))
        write_manifest(base_dir, manifest)
        raise

    print(manifest.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
