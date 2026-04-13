"""Select structure-ready candidates from already-screened inputs."""

from __future__ import annotations

# Schemas are canonical handoff contracts.
# Do not rename, repurpose, or silently widen schema fields once imported downstream.
# Schema changes must be explicit, additive where possible, and updated across all
# dependents in the same packet.

from qops.schemas.candidate import ScreenedCandidate
from qops.schemas.playbook import AllowedPlaybook
from qops.screener.normalize import normalize_candidate
from qops.screener.tradeability import is_tradeable

_EXECUTABLE_PLAYBOOKS: frozenset[AllowedPlaybook] = frozenset(
    {
        AllowedPlaybook.BULL_CALL_SPREAD,
        AllowedPlaybook.BEAR_PUT_SPREAD,
    }
)


def candidate_is_executable(candidate: ScreenedCandidate) -> tuple[bool, str]:
    """Return (flag, reason) for whether the candidate may proceed to structure construction."""
    try:
        normalized = normalize_candidate(candidate)
    except (TypeError, ValueError) as exc:
        return False, f"normalization_failed:{exc}"

    tradeable, tradeable_reason = is_tradeable(normalized)
    if not tradeable:
        return False, tradeable_reason

    if normalized.allowed_playbook not in _EXECUTABLE_PLAYBOOKS:
        return False, "allowed_playbook_not_executable_for_structure_build"

    return True, "candidate_structure_ready"


def select_structure_ready_candidates(
    candidates: list[ScreenedCandidate],
) -> tuple[list[ScreenedCandidate], list[tuple[str, str]]]:
    """
    Return (selected_candidates, skipped_symbol_reasons).

    Preserves input order and never re-ranks candidates.
    """
    selected: list[ScreenedCandidate] = []
    skipped: list[tuple[str, str]] = []

    for candidate in candidates:
        ok, reason = candidate_is_executable(candidate)
        if ok:
            selected.append(candidate)
            continue
        symbol = candidate.symbol if isinstance(candidate, ScreenedCandidate) else "<invalid-candidate>"
        skipped.append((symbol, reason))

    return selected, skipped
