"""Compact formatting for overlay memos in logs and artifacts."""

from __future__ import annotations

from qops.overlay.models import OverlayAssessment


def format_overlay_assessment(overlay: OverlayAssessment) -> str:
    """
    Return a compact human-readable overlay summary.

    Raises:
        TypeError: If overlay is not an OverlayAssessment.
    """
    if not isinstance(overlay, OverlayAssessment):
        raise TypeError("overlay must be OverlayAssessment")

    lines = [
        "Overlay:",
        f"Surface: {overlay.surface_state}",
        f"Market: {overlay.market_state}",
        f"Term: {overlay.term_structure_state}",
        f"Caution: {overlay.caution_flag}",
        f"Downgrade: {overlay.downgrade_flag}",
        f"Summary: {overlay.summary}",
        f"Reason: {overlay.reason}",
    ]
    return "\n".join(lines)
