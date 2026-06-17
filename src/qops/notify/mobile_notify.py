from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from qops.runtime.orb_manifest import OrbRunManifest


class NotificationResult(BaseModel):
    notification_artifact: str
    sent: bool


def send_mobile_notification(
    base_dir: Path,
    manifest: OrbRunManifest,
    advisory_artifact: str,
) -> NotificationResult:
    notification_dir = base_dir / "data/notifications"
    notification_dir.mkdir(parents=True, exist_ok=True)

    notification_path = notification_dir / f"{manifest.run_id}_notification.json"
    latest_path = notification_dir / "latest_notification.json"

    payload = {
        "run_id": manifest.run_id,
        "status": manifest.status,
        "title": "Kidweel morning brief complete",
        "message": (
            "Ingestion and risk classification completed. "
            "Market context and candidate audit are ready for review."
        ),
        "advisory_artifact": advisory_artifact,
        "live_mode_enabled": manifest.live_mode_enabled,
        "broker_mutation_occurred": manifest.broker_mutation_occurred,
    }

    notification_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    latest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return NotificationResult(
        notification_artifact=str(notification_path),
        sent=False,
    )
