"""Select AllowedPlaybook by confirming structure_bias or downgrading to SKIP (never upgrade)."""

from __future__ import annotations

# Schemas are canonical handoff contracts.
# Do not rename, repurpose, or silently widen schema fields once imported downstream.
# Schema changes must be explicit, additive where possible, and updated across all
# dependents in the same packet.

from qops.playbooks.conflicts import has_playbook_conflict
from qops.playbooks.policy import allowed_playbook_domain, environment_is_incomplete
from qops.schemas.environment import EnvironmentSnapshot
from qops.schemas.playbook import AllowedPlaybook, PlaybookDecision, StructureBias


def _structure_to_allowed(structure_bias: StructureBias) -> AllowedPlaybook:
    """Map a structure bias to the same-valued allowed playbook enum member."""
    return AllowedPlaybook(structure_bias.value)


def select_allowed_playbook(
    symbol: str,
    structure_bias: StructureBias,
    environment: EnvironmentSnapshot,
) -> PlaybookDecision:
    """
    Confirm upstream structure_bias or downgrade to SKIP.

    Never upgrades relative to structure_bias. Unmatched combinations resolve to SKIP.
    """
    domain = allowed_playbook_domain(structure_bias)
    conflict_flag, conflict_reason = has_playbook_conflict(structure_bias, environment)

    if structure_bias == StructureBias.SKIP:
        return PlaybookDecision(
            symbol=symbol,
            structure_bias=structure_bias,
            allowed_playbook=AllowedPlaybook.SKIP,
            conflict_flag=False,
            skip_flag=True,
            decision_reason="upstream_structure_skip",
        )

    if environment_is_incomplete(environment):
        return PlaybookDecision(
            symbol=symbol,
            structure_bias=structure_bias,
            allowed_playbook=AllowedPlaybook.SKIP,
            conflict_flag=conflict_flag,
            skip_flag=True,
            decision_reason="incomplete_or_unknown_environment_forces_skip",
        )

    if conflict_flag:
        return PlaybookDecision(
            symbol=symbol,
            structure_bias=structure_bias,
            allowed_playbook=AllowedPlaybook.SKIP,
            conflict_flag=True,
            skip_flag=True,
            decision_reason=conflict_reason,
        )

    if structure_bias == StructureBias.LONG_CALL_PARKED:
        chosen = AllowedPlaybook.LONG_CALL_PARKED
        if chosen not in domain:
            return PlaybookDecision(
                symbol=symbol,
                structure_bias=structure_bias,
                allowed_playbook=AllowedPlaybook.SKIP,
                conflict_flag=True,
                skip_flag=True,
                decision_reason="unmatched_non_executable_state",
            )
        return PlaybookDecision(
            symbol=symbol,
            structure_bias=structure_bias,
            allowed_playbook=chosen,
            conflict_flag=False,
            skip_flag=False,
            decision_reason="confirm_non_executable_long_call_parked",
        )

    if structure_bias == StructureBias.LONG_GAMMA_HEDGE:
        chosen = AllowedPlaybook.LONG_GAMMA_HEDGE
        if chosen not in domain:
            return PlaybookDecision(
                symbol=symbol,
                structure_bias=structure_bias,
                allowed_playbook=AllowedPlaybook.SKIP,
                conflict_flag=True,
                skip_flag=True,
                decision_reason="unmatched_non_executable_state",
            )
        return PlaybookDecision(
            symbol=symbol,
            structure_bias=structure_bias,
            allowed_playbook=chosen,
            conflict_flag=False,
            skip_flag=False,
            decision_reason="confirm_non_executable_long_gamma_hedge",
        )

    if structure_bias in {StructureBias.BULL_CALL_SPREAD, StructureBias.BEAR_PUT_SPREAD}:
        chosen = _structure_to_allowed(structure_bias)
        if chosen not in domain:
            return PlaybookDecision(
                symbol=symbol,
                structure_bias=structure_bias,
                allowed_playbook=AllowedPlaybook.SKIP,
                conflict_flag=True,
                skip_flag=True,
                decision_reason="unmatched_executable_structure",
            )
        return PlaybookDecision(
            symbol=symbol,
            structure_bias=structure_bias,
            allowed_playbook=chosen,
            conflict_flag=False,
            skip_flag=False,
            decision_reason="confirm_executable_playbook_aligned_with_environment",
        )

    return PlaybookDecision(
        symbol=symbol,
        structure_bias=structure_bias,
        allowed_playbook=AllowedPlaybook.SKIP,
        conflict_flag=True,
        skip_flag=True,
        decision_reason="unmatched_structure_bias_resolves_to_skip",
    )
