"""Candidate ingestion pipeline from raw weekly CSV to pre-selected records."""

from __future__ import annotations

from qops.ingestion.loader import load_candidates_from_csv
from qops.ingestion.normalizer import normalize_candidate_record
from qops.ingestion.preselect import preselect_candidates


def run_candidate_ingestion_pipeline(path: str) -> list[dict]:
    """
    Load, validate, normalize, and preselect candidates from a raw file.

    Operator workflow:
    1. Export weekly candidate file (e.g. candidates_v3.csv)
    2. Run ingestion pipeline
    3. Pass results into screener / signal alignment / playbooks
    4. Claude may read resulting candidates as context (memo-only)
    """
    raw_records = load_candidates_from_csv(path)
    normalized = [normalize_candidate_record(record) for record in raw_records]
    return preselect_candidates(normalized)
