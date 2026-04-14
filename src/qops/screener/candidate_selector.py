"""Select structure-ready candidates from already-screened inputs."""

from __future__ import annotations

from enum import Enum

# Schemas are canonical handoff contracts.
# Do not rename, repurpose, or silently widen schema fields once imported downstream.
# Schema changes must be explicit, additive where possible, and updated across all
# dependents in the same packet.

from qops.schemas.candidate import ScreenedCandidate
from qops.schemas.environment import DirectionalBias, IVState, RegimeLabel, SkewState, WallState
from qops.schemas.playbook import AllowedPlaybook, StructureBias
from qops.signals.classifier import GammaRegimeState, PremiumPosture, SignalType, VolTriggerRelation
from qops.signals.alignment import signal_alignment_passes
from qops.screener.normalize import normalize_candidate
from qops.screener.tradeability import is_tradeable

_EXECUTABLE_PLAYBOOKS: frozenset[AllowedPlaybook] = frozenset(
    {
        AllowedPlaybook.BULL_CALL_SPREAD,
        AllowedPlaybook.BEAR_PUT_SPREAD,
    }
)


def _coerce_enum(value: object, enum_cls: type[Enum], field_name: str) -> Enum:
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, str):
        try:
            return enum_cls(value)
        except ValueError as exc:
            raise ValueError(f"invalid {field_name}: {value!r}") from exc
    raise ValueError(f"{field_name} must be {enum_cls.__name__} or str")


def build_screened_candidates_from_raw(records: list[dict]) -> list[ScreenedCandidate]:
    """
    Convert normalized raw candidate dicts into ScreenedCandidate objects.
    """
    required_keys = tuple(ScreenedCandidate.__dataclass_fields__.keys())
    candidates: list[ScreenedCandidate] = []
    for idx, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"record[{idx}] must be dict")
        missing = [key for key in required_keys if key not in record]
        if missing:
            raise ValueError(f"record[{idx}] missing ScreenedCandidate fields: {missing}")

        candidate = ScreenedCandidate(
            symbol=record["symbol"],
            underlying_price=record["underlying_price"],
            dte_target=record["dte_target"],
            expiry_target=record["expiry_target"],
            regime_label=_coerce_enum(record["regime_label"], RegimeLabel, "regime_label"),
            structure_bias=_coerce_enum(record["structure_bias"], StructureBias, "structure_bias"),
            confidence=record["confidence"],
            gamma_ratio=record["gamma_ratio"],
            iv_rank=record["iv_rank"],
            iv_state=_coerce_enum(record["iv_state"], IVState, "iv_state"),
            rr_rank=record["rr_rank"],
            skew_state=_coerce_enum(record["skew_state"], SkewState, "skew_state"),
            iv_1m=record["iv_1m"],
            rv_1m=record["rv_1m"],
            vrp=record["vrp"],
            vrp_z=record["vrp_z"],
            call_wall=record["call_wall"],
            put_wall=record["put_wall"],
            wall_state=_coerce_enum(record["wall_state"], WallState, "wall_state"),
            directional_bias=_coerce_enum(
                record["directional_bias"], DirectionalBias, "directional_bias"
            ),
            signal_type=_coerce_enum(record["signal_type"], SignalType, "signal_type"),
            signal_horizon_days=record["signal_horizon_days"],
            wall_distance_pct=record["wall_distance_pct"],
            signal_strength=record["signal_strength"],
            vol_trigger=record["vol_trigger"],
            vol_trigger_relation=_coerce_enum(
                record["vol_trigger_relation"], VolTriggerRelation, "vol_trigger_relation"
            ),
            gamma_regime_state=_coerce_enum(
                record["gamma_regime_state"], GammaRegimeState, "gamma_regime_state"
            ),
            premium_posture=_coerce_enum(record["premium_posture"], PremiumPosture, "premium_posture"),
            dte_alignment_pass=record["dte_alignment_pass"],
            allowed_playbook=_coerce_enum(record["allowed_playbook"], AllowedPlaybook, "allowed_playbook"),
            tradeability_pass=record["tradeability_pass"],
            liquidity_pass=record["liquidity_pass"],
            screener_reason=record["screener_reason"],
            skip_reason=record["skip_reason"],
        )
        normalized = normalize_candidate(candidate)
        aligned, reason = signal_alignment_passes(normalized)
        if not aligned:
            raise ValueError(f"record[{idx}] signal_alignment_failed:{reason}")
        candidates.append(normalized)
    return candidates


def candidate_is_executable(candidate: ScreenedCandidate) -> tuple[bool, str]:
    """Return (flag, reason) for whether the candidate may proceed to structure construction."""
    try:
        normalized = normalize_candidate(candidate)
    except (TypeError, ValueError) as exc:
        return False, f"normalization_failed:{exc}"

    tradeable, tradeable_reason = is_tradeable(normalized)
    if not tradeable:
        return False, tradeable_reason

    alignment_ok, alignment_reason = signal_alignment_passes(normalized)
    if not alignment_ok:
        return False, alignment_reason

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
