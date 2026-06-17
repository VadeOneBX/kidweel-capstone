from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ALLOWED_SUFFIXES = {".csv", ".xlsx", ".xls"}

ACCEPTED_NAME_PATTERNS = [
    re.compile(r"^morning[_-]?regime.*", re.IGNORECASE),
    re.compile(r"^regime.*", re.IGNORECASE),
    re.compile(r"^spotgamma.*", re.IGNORECASE),
    re.compile(r"^sg[_-]?.*", re.IGNORECASE),
    re.compile(r".*[_-]morning.*", re.IGNORECASE),
]


@dataclass(frozen=True)
class FileContractResult:
    accepted: bool
    reason: str
    normalized_name: str | None = None


def evaluate_ingestion_file(path: Path, run_date: str) -> FileContractResult:
    if not path.is_file():
        return FileContractResult(False, "NOT_A_FILE")

    suffix = path.suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        return FileContractResult(False, f"UNSUPPORTED_SUFFIX:{suffix}")

    stem = path.stem.strip()
    if not stem:
        return FileContractResult(False, "EMPTY_STEM")

    matched = any(pattern.match(stem) for pattern in ACCEPTED_NAME_PATTERNS)
    if not matched:
        return FileContractResult(False, "NAME_PATTERN_MISMATCH")

    safe_stem = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("_").lower()
    normalized_name = f"{run_date}_{safe_stem}{suffix}"

    return FileContractResult(
        accepted=True,
        reason="ACCEPTED",
        normalized_name=normalized_name,
    )
