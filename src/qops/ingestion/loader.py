"""CSV loader for raw weekly candidate records."""

from __future__ import annotations

import csv


def load_candidates_from_csv(path: str) -> list[dict]:
    """
    Load raw candidate records from CSV into list[dict].
    """
    try:
        with open(path, newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            return list(reader)
    except OSError as exc:
        raise ValueError(f"unable to read candidate csv: {path}") from exc
