#!/usr/bin/env python3
"""Deterministic replay sample for BT-C1 — evidence expansion only (no gate changes).

Run:
  PYTHONPATH=src python examples/backtest_sanity_run.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from qops.backtest.runner import run_iterative_backtest
from qops.backtest.replay_context import ReplayContext, validate_replay_context
from qops.schemas.environment import (
    DirectionalBias,
    IVState,
    RegimeLabel,
    SkewState,
    WallState,
)
from qops.schemas.playbook import AllowedPlaybook
from qops.schemas.risk import TradeEvaluation
from qops.schemas.structure import TradeStructureCandidate

SampleSource = Literal[
    "seeded_sanity",
    "historical_replay_derived",
    "manually_constructed_deterministic",
]

_SYMBOLS = ("SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA", "META", "AMD")
_ENV_LABELS = (
    "SQUEEZE_UP_CHEAP_VOL",
    "SELL_PREMIUM_MID_VOL",
    "BUY_PREMIUM_PUTS_RICH",
    "NEUTRAL_BETWEEN_WALLS",
    "SQUEEZE_UP_NEAR_CALL_WALL",
)
_EXIT_CYCLE = ("TP_80", "STOP", "TIME_EXIT", "EXPIRATION_MAX", "EXPIRATION_LOSS")


@dataclass(frozen=True, slots=True)
class TaggedReplay:
    source: SampleSource
    ctx: ReplayContext


def _debit_spread_economics(debit: float = 1.20, width: float = 5.0) -> tuple[float, float, float]:
    max_loss = debit
    max_profit = width - debit
    rr = max_profit / max_loss
    return max_profit, max_loss, rr


def _structure(
    *,
    symbol: str,
    playbook: AllowedPlaybook,
    regime: RegimeLabel,
    confidence: int,
    iv: IVState,
    skew: SkewState,
    wall: WallState,
    bias: DirectionalBias,
    expiry: str,
) -> TradeStructureCandidate:
    max_profit, max_loss, rr = _debit_spread_economics()
    stype = (
        "bullish_debit_spread"
        if playbook == AllowedPlaybook.BULL_CALL_SPREAD
        else "bearish_debit_spread"
    )
    return TradeStructureCandidate(
        symbol=symbol,
        structure_type=stype,
        expiry=expiry,
        width=5.0,
        debit_or_credit=1.20,
        max_profit=max_profit,
        max_loss=max_loss,
        rr_actual=rr,
        regime_label=regime,
        confidence=confidence,
        gamma_ratio=0.42,
        iv_state=iv,
        skew_state=skew,
        wall_state=wall,
        directional_bias=bias,
        allowed_playbook=playbook,
        structure_reason="bt_c1_deterministic_replay_fixture",
    )


def _evaluation(*, symbol: str, playbook: str, pmp: float, rr_actual: float) -> TradeEvaluation:
    max_profit, max_loss, _ = _debit_spread_economics()
    rr_required = 1.35
    return TradeEvaluation(
        symbol=symbol,
        playbook=playbook,
        pmp=pmp,
        rr_required=rr_required,
        rr_actual=rr_actual,
        max_profit=max_profit,
        max_loss=max_loss,
        tp_rule="TP_80",
        sl_rule="STOP",
        time_exit_rule="TIME_EXIT",
        environment_fit=True,
        pass_rr=rr_actual >= rr_required,
        pass_risk=True,
        approved=True,
        approval_reason="bt_c1_replay_record_only",
    )


def _pnl_for_exit(exit_reason: str, idx: int) -> float:
    """Fixed mapping — not tuned to validation thresholds."""
    if exit_reason == "TP_80":
        return 95.0 + float(idx % 9) * 12.0
    if exit_reason == "STOP":
        return -(70.0 + float(idx % 6) * 8.0)
    if exit_reason == "TIME_EXIT":
        return -15.0 if idx % 4 == 0 else 22.0
    if exit_reason == "EXPIRATION_MAX":
        return 180.0 + float(idx % 11) * 5.0
    if exit_reason == "EXPIRATION_LOSS":
        return -(90.0 + float(idx % 7) * 6.0)
    raise ValueError(f"unsupported exit_reason: {exit_reason}")


def _make_context(
    *,
    idx: int,
    source: SampleSource,
    symbol: str,
    playbook: AllowedPlaybook,
    exit_reason: str,
    environment_label: str,
    entry_date: str,
    exit_date: str,
    dte_at_entry: int,
    pmp: float,
    regime: RegimeLabel,
    iv: IVState,
    skew: SkewState,
    wall: WallState,
    bias: DirectionalBias,
) -> TaggedReplay:
    pb = playbook.value
    structure = _structure(
        symbol=symbol,
        playbook=playbook,
        regime=regime,
        confidence=6 + (idx % 4),
        iv=iv,
        skew=skew,
        wall=wall,
        bias=bias,
        expiry="2024-06-21",
    )
    evaluation = _evaluation(symbol=symbol, playbook=pb, pmp=pmp, rr_actual=structure.rr_actual)
    ctx = ReplayContext(
        symbol=symbol,
        playbook=pb,
        structure=structure,
        evaluation=evaluation,
        entry_date=entry_date,
        exit_date=exit_date,
        dte_at_entry=dte_at_entry,
        realized_pnl=_pnl_for_exit(exit_reason, idx),
        exit_reason=exit_reason,
        environment_label=environment_label,
    )
    validate_replay_context(ctx)
    return TaggedReplay(source=source, ctx=ctx)


def _seeded_sanity_trades() -> list[TaggedReplay]:
    """Small fixed set aligned with C13 findings scale (n≈11 subset), not optimized."""
    specs: list[tuple[str, AllowedPlaybook, str, str, float]] = [
        ("SPY", AllowedPlaybook.BULL_CALL_SPREAD, "TP_80", "SQUEEZE_UP_CHEAP_VOL", 110.0),
        ("SPY", AllowedPlaybook.BULL_CALL_SPREAD, "STOP", "SQUEEZE_UP_CHEAP_VOL", -78.0),
        ("QQQ", AllowedPlaybook.BEAR_PUT_SPREAD, "TP_80", "SELL_PREMIUM_MID_VOL", 102.0),
        ("IWM", AllowedPlaybook.BULL_CALL_SPREAD, "TIME_EXIT", "NEUTRAL_BETWEEN_WALLS", 22.0),
        ("AAPL", AllowedPlaybook.BEAR_PUT_SPREAD, "STOP", "BUY_PREMIUM_PUTS_RICH", -86.0),
        ("MSFT", AllowedPlaybook.BULL_CALL_SPREAD, "EXPIRATION_MAX", "SQUEEZE_UP_NEAR_CALL_WALL", 195.0),
        ("NVDA", AllowedPlaybook.BEAR_PUT_SPREAD, "EXPIRATION_LOSS", "SELL_PREMIUM_MID_VOL", -102.0),
        ("META", AllowedPlaybook.BULL_CALL_SPREAD, "TP_80", "NEUTRAL_BETWEEN_WALLS", 118.0),
        ("AMD", AllowedPlaybook.BEAR_PUT_SPREAD, "TIME_EXIT", "BUY_PREMIUM_PUTS_RICH", -15.0),
        ("SPY", AllowedPlaybook.BULL_CALL_SPREAD, "STOP", "SQUEEZE_UP_CHEAP_VOL", -70.0),
        ("QQQ", AllowedPlaybook.BEAR_PUT_SPREAD, "TP_80", "SELL_PREMIUM_MID_VOL", 107.0),
    ]
    out: list[TaggedReplay] = []
    for i, (sym, pb, exit_r, env, pnl) in enumerate(specs):
        structure = _structure(
            symbol=sym,
            playbook=pb,
            regime=RegimeLabel.SQUEEZE_UP if i % 2 == 0 else RegimeLabel.SELL_PREMIUM,
            confidence=7,
            iv=IVState.MID_VOL,
            skew=SkewState.NEUTRAL,
            wall=WallState.BETWEEN_WALLS,
            bias=DirectionalBias.BULLISH_BIAS
            if pb == AllowedPlaybook.BULL_CALL_SPREAD
            else DirectionalBias.BEARISH_BIAS,
            expiry="2024-03-15",
        )
        evaluation = _evaluation(
            symbol=sym, playbook=pb.value, pmp=0.58, rr_actual=structure.rr_actual
        )
        ctx = ReplayContext(
            symbol=sym,
            playbook=pb.value,
            structure=structure,
            evaluation=evaluation,
            entry_date=f"2024-01-{8 + i:02d}",
            exit_date=f"2024-01-{15 + i:02d}",
            dte_at_entry=14 + (i % 5),
            realized_pnl=pnl,
            exit_reason=exit_r,
            environment_label=env,
        )
        validate_replay_context(ctx)
        out.append(TaggedReplay(source="seeded_sanity", ctx=ctx))
    return out


def _manual_deterministic_trades(start_idx: int, count: int) -> list[TaggedReplay]:
    out: list[TaggedReplay] = []
    for j in range(count):
        idx = start_idx + j
        playbook = (
            AllowedPlaybook.BULL_CALL_SPREAD if idx % 2 == 0 else AllowedPlaybook.BEAR_PUT_SPREAD
        )
        exit_reason = _EXIT_CYCLE[idx % len(_EXIT_CYCLE)]
        env = _ENV_LABELS[idx % len(_ENV_LABELS)]
        sym = _SYMBOLS[idx % len(_SYMBOLS)]
        regimes = (
            RegimeLabel.SQUEEZE_UP,
            RegimeLabel.SELL_PREMIUM,
            RegimeLabel.BUY_PREMIUM,
            RegimeLabel.NEUTRAL,
        )
        ivs = (IVState.CHEAP_VOL, IVState.MID_VOL, IVState.EXPENSIVE_VOL)
        regime = regimes[idx % len(regimes)]
        iv = ivs[idx % len(ivs)]
        skew = SkewState.PUTS_RICH if idx % 3 == 0 else SkewState.NEUTRAL
        wall = WallState.NEAR_CALL_WALL if idx % 5 == 0 else WallState.BETWEEN_WALLS
        bias = (
            DirectionalBias.BULLISH_BIAS
            if playbook == AllowedPlaybook.BULL_CALL_SPREAD
            else DirectionalBias.BEARISH_BIAS
        )
        pmp = 0.52 + float(idx % 12) * 0.03
        month = 2 + (idx // 10) % 8
        day = 1 + (idx % 20)
        out.append(
            _make_context(
                idx=idx,
                source="manually_constructed_deterministic",
                symbol=sym,
                playbook=playbook,
                exit_reason=exit_reason,
                environment_label=env,
                entry_date=f"2024-{month:02d}-{day:02d}",
                exit_date=f"2024-{month:02d}-{min(day + 7, 28):02d}",
                dte_at_entry=10 + (idx % 15),
                pmp=pmp,
                regime=regime,
                iv=iv,
                skew=skew,
                wall=wall,
                bias=bias,
            )
        )
    return out


def build_bt_c1_sample() -> list[TaggedReplay]:
    """52 trades: seeded sanity + manual deterministic; no historical CSV replay in repo."""
    seeded = _seeded_sanity_trades()
    manual = _manual_deterministic_trades(start_idx=100, count=41)
    return seeded + manual


def _provenance_counts(tagged: list[TaggedReplay]) -> dict[str, int]:
    counts: dict[str, int] = {
        "seeded_sanity": 0,
        "historical_replay_derived": 0,
        "manually_constructed_deterministic": 0,
    }
    for t in tagged:
        counts[t.source] += 1
    counts["total"] = len(tagged)
    return counts


def main() -> None:
    tagged = build_bt_c1_sample()
    contexts = [t.ctx for t in tagged]
    result = run_iterative_backtest(contexts)
    prov = _provenance_counts(tagged)

    print("BT-C1 deterministic replay sample")
    print("=================================")
    print("Sample provenance (categories are not blended):")
    for key in (
        "seeded_sanity",
        "historical_replay_derived",
        "manually_constructed_deterministic",
        "total",
    ):
        print(f"  {key}: {prov[key]}")
    print()
    print(result["evidence_block"])
    print("Sample limitations:")
    print("  - No historical replay CSVs in repo; historical_replay_derived count is 0.")
    print("  - Outcomes are recorded ReplayContext fixtures, not live market simulation.")
    print("  - Validation uses existing gate logic; metrics are not tuned for PASS.")


if __name__ == "__main__":
    main()
