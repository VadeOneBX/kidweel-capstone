"""Playbook confirmation and downgrade policy (no upgrades, no execution)."""

from __future__ import annotations

from qops.playbooks.conflicts import has_playbook_conflict
from qops.playbooks.policy import (
    ALLOWED_ALLOWED_PLAYBOOKS,
    NON_EXECUTABLE_IN_PACKET,
    allowed_playbook_domain,
    is_non_executable_packet_state,
)
from qops.playbooks.selector import select_allowed_playbook

__all__ = [
    "ALLOWED_ALLOWED_PLAYBOOKS",
    "NON_EXECUTABLE_IN_PACKET",
    "allowed_playbook_domain",
    "has_playbook_conflict",
    "is_non_executable_packet_state",
    "select_allowed_playbook",
]
