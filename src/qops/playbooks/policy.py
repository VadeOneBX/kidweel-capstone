"""Explicit non-upgrading playbook policy: confirm structure_bias or downgrade to SKIP only."""

from __future__ import annotations

# Schemas are canonical handoff contracts.
# Do not rename, repurpose, or silently widen schema fields once imported downstream.
# Schema changes must be explicit, additive where possible, and updated across all
# dependents in the same packet.

from qops.schemas.environment import EnvironmentSnapshot, HostageState, WallState
from qops.schemas.playbook import AllowedPlaybook, StructureBias

# Policy truths (MCP-C5):
# 1. structure_bias is upstream intent and must not be replaced downstream.
# 2. allowed_playbook may confirm structure_bias or downgrade to SKIP only (never upgrade).
# 3. LONG_CALL_PARKED remains non-executable in this packet (may persist as allowed state).
# 4. LONG_GAMMA_HEDGE remains non-executable in this packet (may persist as allowed state).
# 5. UNKNOWN / incomplete / conflicting environment resolves to SKIP for new risk.
# 6. regime_label is canonical and must not be recomputed (read-only on EnvironmentSnapshot).

NON_EXECUTABLE_IN_PACKET: frozenset[AllowedPlaybook] = frozenset(
    {
        AllowedPlaybook.LONG_CALL_PARKED,
        AllowedPlaybook.LONG_GAMMA_HEDGE,
    }
)

NON_EXECUTABLE_STRUCTURE_IN_PACKET: frozenset[StructureBias] = frozenset(
    {
        StructureBias.LONG_CALL_PARKED,
        StructureBias.LONG_GAMMA_HEDGE,
    }
)

ALLOWED_ALLOWED_PLAYBOOKS: dict[StructureBias, frozenset[AllowedPlaybook]] = {
    StructureBias.BULL_CALL_SPREAD: frozenset({AllowedPlaybook.BULL_CALL_SPREAD, AllowedPlaybook.SKIP}),
    StructureBias.BEAR_PUT_SPREAD: frozenset({AllowedPlaybook.BEAR_PUT_SPREAD, AllowedPlaybook.SKIP}),
    StructureBias.LONG_CALL_PARKED: frozenset({AllowedPlaybook.LONG_CALL_PARKED, AllowedPlaybook.SKIP}),
    StructureBias.LONG_GAMMA_HEDGE: frozenset({AllowedPlaybook.LONG_GAMMA_HEDGE, AllowedPlaybook.SKIP}),
    StructureBias.SKIP: frozenset({AllowedPlaybook.SKIP}),
}


def allowed_playbook_domain(structure_bias: StructureBias) -> frozenset[AllowedPlaybook]:
    """Return the set of AllowedPlaybook values permitted without upgrading from structure_bias."""
    return ALLOWED_ALLOWED_PLAYBOOKS[structure_bias]


def is_non_executable_packet_state(playbook: AllowedPlaybook) -> bool:
    """Return True if playbook is a persisted but non-executable packet state."""
    return playbook in NON_EXECUTABLE_IN_PACKET


def environment_is_incomplete(environment: EnvironmentSnapshot) -> bool:
    """
    Return True when wall or hostage state is UNKNOWN or environment_reason signals mismatch.

    Used to force SKIP for unmatched / incomplete classification outcomes.
    """
    if environment.wall_state == WallState.UNKNOWN:
        return True
    if environment.hostage_state == HostageState.UNKNOWN:
        return True
    if "mismatch" in environment.environment_reason:
        return True
    if "invalid_" in environment.environment_reason:
        return True
    return False
