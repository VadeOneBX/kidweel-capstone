from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class RiskGuardResult(BaseModel):
    risk_audit_artifact: str


def run_risk_guard(
    base_dir: Path,
    run_id: str,
    candidates_artifact: str,
    paper_only: bool = True,
) -> RiskGuardResult:
    _ = candidates_artifact

    if not paper_only:
        raise RuntimeError("PAPER_ONLY_REQUIRED")

    risk_path = base_dir / "data/processed/risk" / f"{run_id}_risk_audit.csv"
    risk_path.parent.mkdir(parents=True, exist_ok=True)

    risk_path.write_text(
        "run_id,paper_only,status\n" f"{run_id},{paper_only},PLACEHOLDER_RISK_GUARD\n"
    )

    return RiskGuardResult(risk_audit_artifact=str(risk_path))
