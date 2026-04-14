"""Weekly candidate ingestion modules."""

from __future__ import annotations

from qops.ingestion.loader import load_candidates_from_csv
from qops.ingestion.normalizer import normalize_candidate_record
from qops.ingestion.pipeline import run_candidate_ingestion_pipeline
from qops.ingestion.preselect import preselect_candidates
from qops.ingestion.schema import OPTIONAL_FIELDS, REQUIRED_FIELDS, validate_candidate_schema

__all__ = [
    "OPTIONAL_FIELDS",
    "REQUIRED_FIELDS",
    "load_candidates_from_csv",
    "normalize_candidate_record",
    "preselect_candidates",
    "run_candidate_ingestion_pipeline",
    "validate_candidate_schema",
]
