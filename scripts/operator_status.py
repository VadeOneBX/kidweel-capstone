from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from qops.advisory.subagent_ideas import (
    TIER3_AGENTS,
    count_idea_types,
    load_tier3_ideas,
)
from qops.runtime.orb_manifest import manifest_path, read_manifest, read_manifest_by_run_id


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dir", default=".")
    parser.add_argument("--date", default=None)
    parser.add_argument(
        "--run-id",
        default=None,
        help="Read immutable manifest for this run_id instead of latest orb_manifest.json",
    )
    parser.add_argument(
        "--ideas-summary",
        action="store_true",
        help="Read-only summary of latest post-ORB Tier 3 idea artifacts",
    )
    return parser.parse_args()


def _parse_ideas_path(path: Path) -> tuple[str, str, str] | None:
    name = path.name
    if not name.endswith("_ideas.json"):
        return None
    stem = name[: -len("_ideas.json")]
    for agent_id in TIER3_AGENTS:
        suffix = f"_{agent_id}"
        if stem.endswith(suffix):
            run_id = stem[: -len(suffix)]
            if not run_id:
                return None
            return path.parent.name, run_id, agent_id
    return None


def _find_latest_ideas_run(base_dir: Path) -> tuple[str, str] | None:
    runs_dir = base_dir / "data" / "runs"
    if not runs_dir.is_dir():
        return None

    latest_mtime_by_run: dict[tuple[str, str], float] = {}
    for path in runs_dir.glob("*/*_ideas.json"):
        parsed = _parse_ideas_path(path)
        if parsed is None:
            continue
        run_date, run_id, _ = parsed
        key = (run_date, run_id)
        mtime = path.stat().st_mtime
        latest_mtime_by_run[key] = max(latest_mtime_by_run.get(key, 0.0), mtime)

    if not latest_mtime_by_run:
        return None

    return max(latest_mtime_by_run.items(), key=lambda item: (item[0][0], item[1]))[0]


def print_ideas_summary(base_dir: Path) -> int:
    latest = _find_latest_ideas_run(base_dir)
    if latest is None:
        print("NO_IDEA_ARTIFACTS_FOUND")
        return 0

    run_date, run_id = latest
    artifacts = load_tier3_ideas(base_dir, run_date, run_id)
    if not artifacts:
        print("NO_IDEA_ARTIFACTS_FOUND")
        return 0

    counts = count_idea_types(artifacts)
    print(
        f"run_date={run_date} run_id={run_id} agents={len(artifacts)} "
        f"PROPOSE={counts['PROPOSE']} WATCH={counts['WATCH']} PASS={counts['PASS']}"
    )
    return 0


def main() -> int:
    args = parse_args()
    base_dir = Path(args.base_dir).resolve()

    if args.ideas_summary:
        return print_ideas_summary(base_dir)

    run_date = args.date or datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")

    if args.run_id:
        path = base_dir / "data" / "runs" / run_date / f"{args.run_id}_orb_manifest.json"
        if not path.exists():
            print(f"NO_MANIFEST_FOUND: {path}")
            return 1
        print(read_manifest_by_run_id(base_dir, run_date, args.run_id).model_dump_json(indent=2))
        return 0

    path = manifest_path(base_dir, run_date)
    if not path.exists():
        print(f"NO_MANIFEST_FOUND: {path}")
        return 1

    print(read_manifest(base_dir, run_date).model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
