#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from qops.runtime.redis_bus import RedisBus
from qops.runtime.settings import settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Kidweel cron trigger.")
    parser.add_argument("--source", default="manual")
    parser.add_argument("--name", default="orb_wake")
    parser.add_argument("--dry-run", action="store_true", default=True)
    args = parser.parse_args()

    if not settings.qops_paper_only:
        raise SystemExit("PAPER_ONLY_REQUIRED")

    payload = {
        "name": args.name,
        "source": args.source,
        "dry_run": args.dry_run,
        "paper_only": settings.qops_paper_only,
        "ts": time.time(),
    }

    logs = Path("logs")
    logs.mkdir(exist_ok=True)
    with (logs / "cron_trigger_latest.json").open("w") as f:
        json.dump(payload, f, indent=2)

    bus = RedisBus()
    bus.publish("qops.cron", payload)

    print(json.dumps({"ok": True, **payload}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
