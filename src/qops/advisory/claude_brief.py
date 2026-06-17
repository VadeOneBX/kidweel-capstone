from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from qops.runtime.orb_manifest import OrbRunManifest


class ClaudeBriefResult(BaseModel):
    advisory_artifact: str


def generate_claude_brief(
    base_dir: Path,
    manifest: OrbRunManifest,
) -> ClaudeBriefResult:
    required = [
        manifest.context_artifact,
        manifest.candidates_artifact,
        manifest.risk_audit_artifact,
    ]

    missing = [p for p in required if not p or not Path(p).exists()]
    if missing:
        raise RuntimeError(f"ADVISORY_BLOCKED_MISSING_ARTIFACTS:{missing}")

    advisory_dir = base_dir / "data/advisory"
    advisory_dir.mkdir(parents=True, exist_ok=True)

    advisory_path = advisory_dir / f"{manifest.run_id}_claude_brief.md"
    latest_path = advisory_dir / "latest_claude_brief.md"

    body = f"""# Kidweel Morning Brief

Run ID: `{manifest.run_id}`  
Run status: `{manifest.status}`  
Mode: `{manifest.mode}`

## Intake

- Files found: {manifest.files_found}
- Files staged: {manifest.files_staged}
- Files rejected: {manifest.files_rejected}

## Artifacts

- Context: `{manifest.context_artifact}`
- Candidates: `{manifest.candidates_artifact}`
- Risk audit: `{manifest.risk_audit_artifact}`

## Guardrails

- Live mode enabled: `{manifest.live_mode_enabled}`
- Broker mutation occurred: `{manifest.broker_mutation_occurred}`

## Advisory

Market context has been established from deterministic ingestion artifacts.

Candidate proposals and risk classification are available for operator review.

No live execution path was enabled.
"""

    advisory_path.write_text(body, encoding="utf-8")
    latest_path.write_text(body, encoding="utf-8")

    return ClaudeBriefResult(advisory_artifact=str(advisory_path))
