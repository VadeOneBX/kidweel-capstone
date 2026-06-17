from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class DailyPipelineResult(BaseModel):
    context_artifact: str
    candidates_artifact: str


def run_daily_pipeline(
    base_dir: Path,
    run_id: str,
    staged_files: list[str],
    dry_run: bool = True,
) -> DailyPipelineResult:
    """
    Adapter around existing ingestion/context/candidate generation flow.

    Replace placeholder writes with calls into current repo pipeline when wired.
    Never call broker mutation here.
    """
    _ = staged_files
    _ = dry_run

    context_path = base_dir / "data/processed/context" / f"{run_id}_context.csv"
    candidates_path = base_dir / "data/processed/candidates" / f"{run_id}_candidates.csv"

    context_path.parent.mkdir(parents=True, exist_ok=True)
    candidates_path.parent.mkdir(parents=True, exist_ok=True)

    context_path.write_text("run_id,status\n" f"{run_id},PLACEHOLDER_CONTEXT\n")
    candidates_path.write_text("run_id,status\n" f"{run_id},PLACEHOLDER_CANDIDATES\n")

    return DailyPipelineResult(
        context_artifact=str(context_path),
        candidates_artifact=str(candidates_path),
    )
