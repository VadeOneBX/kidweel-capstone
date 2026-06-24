from __future__ import annotations

import json
import os
import platform
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from pydantic import BaseModel

from qops.runtime.orb_manifest import OrbRunManifest


class NotificationResult(BaseModel):
    notification_artifact: str
    sent: bool


def _try_macos_notification(title: str, message: str) -> bool:
    if platform.system() != "Darwin":
        return False
    script = f'display notification "{message}" with title "{title}"'
    try:
        subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def _try_ntfy_publish(title: str, message: str) -> bool:
    topic = os.environ.get("KIDWEEL_NTFY_TOPIC", "").strip()
    if not topic:
        return False
    server = os.environ.get("KIDWEEL_NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    url = f"{server}/{topic}"
    body = f"{title}\n\n{message}".encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Title": title, "Priority": "default"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10):
            return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _try_pushover(title: str, message: str) -> bool:
    token = os.environ.get("KIDWEEL_PUSHOVER_TOKEN", "").strip()
    user = os.environ.get("KIDWEEL_PUSHOVER_USER", "").strip()
    if not token or not user:
        return False
    payload = urllib.parse.urlencode(
        {"token": token, "user": user, "title": title, "message": message}
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://api.pushover.net/1/messages.json",
        data=payload,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10):
            return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def deliver_notification_transport(title: str, message: str) -> bool:
    """Best-effort transport after artifact write (ntfy → Pushover → macOS)."""
    if _try_ntfy_publish(title, message):
        return True
    if _try_pushover(title, message):
        return True
    return _try_macos_notification(title, message)


def send_mobile_notification(
    base_dir: Path,
    manifest: OrbRunManifest,
    advisory_artifact: str,
    *,
    skip_transport: bool = False,
) -> NotificationResult:
    _ = base_dir

    notification_dir = base_dir / "data/notifications"
    notification_dir.mkdir(parents=True, exist_ok=True)

    notification_path = notification_dir / f"{manifest.run_id}_notification.json"
    latest_path = notification_dir / "latest_notification.json"

    title = "Kidweel morning brief complete"
    message = (
        "Ingestion and risk classification completed. "
        "Market context and candidate audit are ready for review."
    )

    payload = {
        "run_id": manifest.run_id,
        "status": manifest.status,
        "title": title,
        "message": message,
        "advisory_artifact": advisory_artifact,
        "live_mode_enabled": manifest.live_mode_enabled,
        "broker_mutation_occurred": manifest.broker_mutation_occurred,
        "notification_sent": False,
    }

    notification_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    latest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    sent = False
    if not skip_transport:
        sent = deliver_notification_transport(title, message)
        payload["notification_sent"] = sent
        notification_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        latest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return NotificationResult(
        notification_artifact=str(notification_path),
        sent=sent,
    )
