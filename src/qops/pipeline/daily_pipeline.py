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

_RUN_ID_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})-")


class DailyPipelineResult(BaseModel):
    context_artifact: str
    candidates_artifact: str


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

    contexts_to_dataframe(contexts).to_csv(context_path, index=False)

    replay_candidates = build_replay_candidates(contexts)
    candidates_to_dataframe(replay_candidates).to_csv(candidates_path, index=False)

    return DailyPipelineResult(
        context_artifact=str(context_path),
        candidates_artifact=str(candidates_path),
    )
