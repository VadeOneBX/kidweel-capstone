from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel

from qops.backtest.spotgamma_replay_builder import (
    build_replay_candidates,
    candidates_to_dataframe,
)
from qops.ingest.spotgamma_normalize import contexts_to_dataframe
from qops.ingest.staged_intake import load_contexts_from_staged_files, session_date_from_staged_path
from qops.pipeline.alpaca_hydration_loop import (
    expressions_artifact_path,
    run_alpaca_expression_hydration,
)
from qops.risk.guard_runner import enrich_morning_candidate_export, hydrate_morning_replay_candidates

_RUN_ID_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})-")


class DailyPipelineResult(BaseModel):
    context_artifact: str
    candidates_artifact: str
    expressions_artifact: str


def _default_session_date(run_id: str) -> str:
    match = _RUN_ID_DATE.match(run_id)
    if match:
        return match.group(1)
    return ""


def run_daily_pipeline(
    base_dir: Path,
    run_id: str,
    staged_files: list[str],
    dry_run: bool = True,
) -> DailyPipelineResult:
    """
    Staged SpotGamma file → parse/normalize → context → replay candidate table.

    Never calls broker mutation.
    """
    _ = dry_run

    session_date = _default_session_date(run_id)
    if not session_date and staged_files:
        session_date = session_date_from_staged_path(Path(staged_files[0]), "")

    spotgamma_root = base_dir / "data/spotgamma"
    contexts = load_contexts_from_staged_files(
        staged_files,
        default_session_date=session_date,
        spotgamma_root=spotgamma_root,
    )

    context_path = base_dir / "data/processed/context" / f"{run_id}_context.csv"
    candidates_path = base_dir / "data/processed/candidates" / f"{run_id}_candidates.csv"
    context_path.parent.mkdir(parents=True, exist_ok=True)
    candidates_path.parent.mkdir(parents=True, exist_ok=True)

    context_df = contexts_to_dataframe(contexts)
    context_df.to_csv(context_path, index=False)

    replay_candidates = build_replay_candidates(contexts)
    candidate_df = enrich_morning_candidate_export(
        candidates_to_dataframe(replay_candidates),
        run_id=run_id,
    )
    candidate_df = hydrate_morning_replay_candidates(candidate_df, context_df)
    expressions_path = expressions_artifact_path(base_dir, run_id)
    hydration = run_alpaca_expression_hydration(
        candidate_df,
        fetch=True,
        expressions_output_path=expressions_path,
    )
    candidate_df = hydration.candidate_df
    candidate_df.to_csv(candidates_path, index=False)

    return DailyPipelineResult(
        context_artifact=str(context_path),
        candidates_artifact=str(candidates_path),
        expressions_artifact=str(expressions_path),
    )
