from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Canonical delayed-chain CSV columns (must match C13E / mcp_chain_summary expectations).
REQUIRED_CHAIN_COLUMNS: tuple[str, ...] = ("expiration", "strike", "option_type", "open_interest")


@dataclass(frozen=True, slots=True)
class ChainSnapshotFetchSummary:
    """Compact result from a chain snapshot fetch pass (research-only, no execution)."""

    requested: int
    fetched: int
    skipped: list[str]
    output_root: str


def summary_to_dict(summary: ChainSnapshotFetchSummary) -> dict[str, Any]:
    """Serialize :class:`ChainSnapshotFetchSummary` to a JSON-friendly dict."""

    return {
        "requested": summary.requested,
        "fetched": summary.fetched,
        "skipped": list(summary.skipped),
        "output_root": summary.output_root,
    }
