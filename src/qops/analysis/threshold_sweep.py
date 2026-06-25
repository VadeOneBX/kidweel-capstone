"""Non-destructive threshold sweep on staged spread candidates (THRESH-C1)."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Callable, Literal

import pandas as pd

from qops.backtest.canonical_refresh import advisory_group_from_profile
from qops.risk.pmp_policy import min_rr_for_pmp
from qops.risk.paper_approval import SpreadCandidateInputRow, load_spread_candidate_rows
from qops.schemas.playbook import AllowedPlaybook
from qops.execution.paper_payload_candidate import load_paper_approval_rows

PROVENANCE_TAG = "thresh_c1_threshold_sweep"

AdvisoryGroup = Literal[
    "SQUEEZE_CANDIDATES",
    "VOLATILITY_RISK_PREMIUM",
    "REVERSE_RISK_PREMIUM",
    "UNKNOWN",
]

_CANONICAL_STRUCTURES = frozenset(
    {
        AllowedPlaybook.BULL_CALL_SPREAD.value,
        AllowedPlaybook.BEAR_PUT_SPREAD.value,
        AllowedPlaybook.BULL_PUT_CREDIT_SPREAD.value,
        AllowedPlaybook.BEAR_CALL_CREDIT_SPREAD.value,
    }
)

_ECONOMICS_INVALID_REASONS = frozenset(
    {
        "invalid_max_loss",
        "invalid_max_profit",
        "missing_probability_of_profit",
        "missing_pmp",
    }
)


@dataclass(frozen=True, slots=True)
class EnrichedSweepRow:
    candidate_id: str
    spread: SpreadCandidateInputRow
    pmp: float | None
    expected_value: float | None
    min_rr_required: float | None
    reward_risk: float | None
    bid_ask_spread_pct: float | None
    spread_delta: float | None
    advisory_group: AdvisoryGroup
    source_profile: str
    candidate_pass: bool
    math_status: str
    probability_status: str
    ev_status: str
    approved_in_file: bool


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    scenario_name: str
    total_input_rows: int
    rows_with_required_fields: int
    pass_count: int
    pass_rate: float
    candidate_pass_count: int
    approved_count: int
    avg_reward_risk: float | None
    median_reward_risk: float | None
    avg_pmp: float | None
    median_pmp: float | None
    avg_expected_value: float | None
    median_expected_value: float | None
    avg_bid_ask_spread_pct: float | None
    by_structure: dict[str, int]
    by_advisory_group: dict[str, int]
    missing_field_counts: dict[str, int]
    top_10_survivors: list[dict[str, Any]]


def _parse_float(raw: object) -> float | None:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    try:
        out = float(raw)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _parse_str(raw: object, default: str = "") -> str:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return default
    return str(raw).strip()


def _bid_ask_spread_pct(bid: float | None, ask: float | None) -> float | None:
    if bid is None or ask is None or bid <= 0 or ask <= 0 or ask < bid:
        return None
    mid = (bid + ask) / 2.0
    if mid <= 0:
        return None
    return (ask - bid) / mid


def _load_greeks_leg_index(path: Path) -> dict[str, dict[str, float | str | None]]:
    if not path.is_file():
        return {}
    df = pd.read_csv(path)
    out: dict[str, dict[str, float | str | None]] = {}
    for _, series in df.iterrows():
        opt = _parse_str(series.get("option_symbol"))
        if not opt:
            continue
        out[opt] = {
            "bid": _parse_float(series.get("bid")),
            "ask": _parse_float(series.get("ask")),
            "delta": _parse_float(series.get("delta")),
            "source_profile": _parse_str(series.get("source_profile")),
        }
    return out


def _sym_date_profiles(greeks_index: dict[str, dict[str, float | str | None]], path: Path) -> dict[tuple[str, str], str]:
    if not path.is_file():
        return {}
    df = pd.read_csv(path)
    out: dict[tuple[str, str], str] = {}
    for _, series in df.iterrows():
        sym = _parse_str(series.get("underlying_symbol")).upper()
        td = _parse_str(series.get("trade_date"))
        profile = _parse_str(series.get("source_profile"))
        if sym and td and profile:
            out[(sym, td)] = profile
    return out


def _spread_bid_ask_pct(
    long_sym: str,
    short_sym: str,
    greeks: dict[str, dict[str, float | str | None]],
) -> float | None:
    long_leg = greeks.get(long_sym.strip())
    short_leg = greeks.get(short_sym.strip())
    if not long_leg or not short_leg:
        return None
    long_pct = _bid_ask_spread_pct(
        _parse_float(long_leg.get("bid")), _parse_float(long_leg.get("ask"))
    )
    short_pct = _bid_ask_spread_pct(
        _parse_float(short_leg.get("bid")), _parse_float(short_leg.get("ask"))
    )
    if long_pct is None and short_pct is None:
        return None
    if long_pct is None:
        return short_pct
    if short_pct is None:
        return long_pct
    return max(long_pct, short_pct)


def _spread_delta(
    long_sym: str,
    short_sym: str,
    structure_type: str,
    greeks: dict[str, dict[str, float | str | None]],
) -> float | None:
    long_leg = greeks.get(long_sym.strip())
    short_leg = greeks.get(short_sym.strip())
    if not long_leg or not short_leg:
        return None
    ld = _parse_float(long_leg.get("delta"))
    sd = _parse_float(short_leg.get("delta"))
    if ld is None or sd is None:
        return None
    if structure_type in {
        AllowedPlaybook.BULL_CALL_SPREAD.value,
        AllowedPlaybook.BEAR_PUT_SPREAD.value,
    }:
        return ld - sd
    return sd - ld


def _expected_value(pmp: float, max_profit: float, max_loss: float) -> float:
    return pmp * max_profit - (1.0 - pmp) * max_loss


def _candidate_id(row: SpreadCandidateInputRow) -> str:
    key = "|".join(
        [
            row.underlying_symbol.upper(),
            row.trade_date,
            row.structure_type,
            row.long_option_symbol,
            row.short_option_symbol,
        ]
    )
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _approval_lookup(approvals_path: Path) -> dict[str, bool]:
    rows = load_paper_approval_rows(approvals_path)
    out: dict[str, bool] = {}
    for r in rows:
        key = "|".join(
            [
                r.symbol.upper(),
                r.trade_date,
                r.structure_type,
                r.long_leg_symbol,
                r.short_leg_symbol,
            ]
        )
        approved = r.approval_status == "APPROVED_FOR_PAPER_REVIEW"
        out[key] = approved
    return out


def _economics_invalid(failure_reasons: str) -> bool:
    parts = {p.strip() for p in (failure_reasons or "").split("|") if p.strip()}
    return bool(parts & _ECONOMICS_INVALID_REASONS)


def _core_eligible(row: EnrichedSweepRow) -> bool:
    s = row.spread
    if s.structure_type not in _CANONICAL_STRUCTURES:
        return False
    if row.pmp is None:
        return False
    if row.expected_value is None or not math.isfinite(row.expected_value):
        return False
    if row.reward_risk is None or not math.isfinite(row.reward_risk):
        return False
    if s.max_loss is None or s.max_loss <= 0:
        return False
    if s.max_profit is None:
        return False
    if _economics_invalid(s.failure_reasons):
        return False
    return True


def _finite_mean(values: list[float | None]) -> float | None:
    nums = [v for v in values if v is not None and math.isfinite(v)]
    if not nums:
        return None
    return sum(nums) / len(nums)


def _finite_median(values: list[float | None]) -> float | None:
    nums = [v for v in values if v is not None and math.isfinite(v)]
    if not nums:
        return None
    return float(statistics.median(nums))


def enrich_spread_candidates(
    spreads_path: Path,
    *,
    greeks_path: Path | None = None,
    approvals_path: Path | None = None,
    limit: int | None = None,
) -> list[EnrichedSweepRow]:
    spread_rows = load_spread_candidate_rows(spreads_path)
    if limit is not None and limit > 0:
        spread_rows = spread_rows[:limit]

    greeks_path = greeks_path or Path("data/processed/alpaca_greeks_candidates.csv")
    greeks_index = _load_greeks_leg_index(greeks_path)
    sym_date = _sym_date_profiles(greeks_index, greeks_path)
    approval_map = _approval_lookup(approvals_path) if approvals_path and approvals_path.is_file() else {}

    extra_df = pd.read_csv(spreads_path) if spreads_path.is_file() else None
    enriched: list[EnrichedSweepRow] = []
    for i, s in enumerate(spread_rows):
        series = extra_df.iloc[i] if extra_df is not None and i < len(extra_df) else None
        pmp = s.pmp_for_gate
        if pmp is None and series is not None:
            pmp = _parse_float(series.get("probability_of_profit"))
        ev: float | None = None
        if series is not None:
            ev = _parse_float(series.get("expected_value"))
        if ev is None and pmp is not None and s.max_profit is not None and s.max_loss is not None:
            ev = _expected_value(pmp, s.max_profit, s.max_loss)
        min_rr: float | None = None
        if pmp is not None:
            try:
                min_rr = min_rr_for_pmp(pmp)
            except ValueError:
                min_rr = None

        ba_pct: float | None = None
        if series is not None:
            ba_pct = _parse_float(series.get("bid_ask_spread_pct"))
        if ba_pct is None:
            ba_pct = _spread_bid_ask_pct(s.long_option_symbol, s.short_option_symbol, greeks_index)

        sym = s.underlying_symbol.strip().upper()
        profile = sym_date.get((sym, s.trade_date.strip()), "")
        if not profile:
            long_meta = greeks_index.get(s.long_option_symbol.strip(), {})
            profile = _parse_str(long_meta.get("source_profile"))

        approval_key = "|".join(
            [sym, s.trade_date, s.structure_type, s.long_option_symbol, s.short_option_symbol]
        )
        math_status = _parse_str(series.get("math_status")) if series is not None else ""
        if not math_status:
            math_status = "PASS" if s.candidate_pass else (
                "INCOMPLETE" if s.probability_status == "INCOMPLETE" else "WATCH"
            )

        enriched.append(
            EnrichedSweepRow(
                candidate_id=_candidate_id(s),
                spread=s,
                pmp=pmp,
                expected_value=ev,
                min_rr_required=min_rr,
                reward_risk=s.reward_risk,
                bid_ask_spread_pct=ba_pct,
                spread_delta=_spread_delta(
                    s.long_option_symbol, s.short_option_symbol, s.structure_type, greeks_index
                ),
                advisory_group=advisory_group_from_profile(profile),
                source_profile=profile,
                candidate_pass=s.candidate_pass,
                math_status=math_status,
                probability_status=s.probability_status,
                ev_status=s.ev_status,
                approved_in_file=approval_map.get(approval_key, False),
            )
        )
    return enriched


@dataclass(frozen=True, slots=True)
class ScenarioSpec:
    name: str
    requires_bid_ask: bool
    predicate: Callable[[EnrichedSweepRow], bool]


def _build_scenarios() -> list[ScenarioSpec]:
    specs: list[ScenarioSpec] = [
        ScenarioSpec(
            "baseline",
            False,
            lambda r: _core_eligible(r) and r.candidate_pass,
        ),
    ]
    for floor in (1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0):
        label = f"rr_gte_{floor:.2f}".replace(".", "_")
        specs.append(
            ScenarioSpec(
                label,
                False,
                lambda r, f=floor: _core_eligible(r)
                and r.reward_risk is not None
                and r.reward_risk >= f,
            )
        )
    for floor in (0.0, 0.05, 0.10, 0.25):
        label = f"ev_gte_{floor:.2f}".replace(".", "_")
        specs.append(
            ScenarioSpec(
                label,
                False,
                lambda r, f=floor: _core_eligible(r)
                and r.expected_value is not None
                and r.expected_value >= f,
            )
        )
    for ceiling in (0.50, 0.35, 0.25, 0.15):
        label = f"bid_ask_spread_pct_lte_{ceiling:.2f}".replace(".", "_")
        specs.append(
            ScenarioSpec(
                label,
                True,
                lambda r, c=ceiling: _core_eligible(r)
                and r.bid_ask_spread_pct is not None
                and r.bid_ask_spread_pct <= c,
            )
        )
    combined: list[tuple[str, bool, Callable[[EnrichedSweepRow], bool]]] = [
        (
            "ev_gte_0_and_rr_gte_2_00",
            False,
            lambda r: _core_eligible(r)
            and r.expected_value is not None
            and r.expected_value >= 0.0
            and r.reward_risk is not None
            and r.reward_risk >= 2.0,
        ),
        (
            "ev_gte_0_and_bid_ask_spread_pct_lte_0_50",
            True,
            lambda r: _core_eligible(r)
            and r.expected_value is not None
            and r.expected_value >= 0.0
            and r.bid_ask_spread_pct is not None
            and r.bid_ask_spread_pct <= 0.50,
        ),
        (
            "ev_gte_0_and_bid_ask_spread_pct_lte_0_25",
            True,
            lambda r: _core_eligible(r)
            and r.expected_value is not None
            and r.expected_value >= 0.0
            and r.bid_ask_spread_pct is not None
            and r.bid_ask_spread_pct <= 0.25,
        ),
        (
            "ev_gte_0_and_rr_gte_2_00_and_bid_ask_spread_pct_lte_0_50",
            True,
            lambda r: _core_eligible(r)
            and r.expected_value is not None
            and r.expected_value >= 0.0
            and r.reward_risk is not None
            and r.reward_risk >= 2.0
            and r.bid_ask_spread_pct is not None
            and r.bid_ask_spread_pct <= 0.50,
        ),
        (
            "ev_gte_0_and_rr_gte_2_00_and_bid_ask_spread_pct_lte_0_25",
            True,
            lambda r: _core_eligible(r)
            and r.expected_value is not None
            and r.expected_value >= 0.0
            and r.reward_risk is not None
            and r.reward_risk >= 2.0
            and r.bid_ask_spread_pct is not None
            and r.bid_ask_spread_pct <= 0.25,
        ),
        (
            "ev_gte_0_and_rr_gte_min_rr_required_and_bid_ask_spread_pct_lte_0_25",
            True,
            lambda r: _core_eligible(r)
            and r.expected_value is not None
            and r.expected_value >= 0.0
            and r.min_rr_required is not None
            and r.reward_risk is not None
            and r.reward_risk >= r.min_rr_required
            and r.bid_ask_spread_pct is not None
            and r.bid_ask_spread_pct <= 0.25,
        ),
    ]
    for name, req_ba, pred in combined:
        specs.append(ScenarioSpec(name, req_ba, pred))
    return specs


def _missing_fields(row: EnrichedSweepRow, *, requires_bid_ask: bool) -> dict[str, int]:
    counts: dict[str, int] = {}
    if row.pmp is None:
        counts["missing_pmp"] = 1
    if row.expected_value is None:
        counts["missing_expected_value"] = 1
    if row.reward_risk is None:
        counts["missing_reward_risk"] = 1
    if row.spread.max_loss is None or row.spread.max_loss <= 0:
        counts["invalid_max_loss"] = 1
    if row.spread.max_profit is None:
        counts["missing_max_profit"] = 1
    if requires_bid_ask and row.bid_ask_spread_pct is None:
        counts["missing_bid_ask_spread_pct"] = 1
    return counts


def _rows_with_required_fields(row: EnrichedSweepRow, *, requires_bid_ask: bool) -> bool:
    if row.spread.structure_type not in _CANONICAL_STRUCTURES:
        return False
    if requires_bid_ask and row.bid_ask_spread_pct is None:
        return False
    return True


def _top_survivors(
    survivors: list[EnrichedSweepRow],
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    ranked = sorted(
        survivors,
        key=lambda r: (
            r.reward_risk if r.reward_risk is not None else -1.0,
            r.pmp if r.pmp is not None else -1.0,
            r.spread_delta if r.spread_delta is not None else -1.0,
        ),
        reverse=True,
    )
    out: list[dict[str, Any]] = []
    for r in ranked[:limit]:
        out.append(
            {
                "candidate_id": r.candidate_id,
                "symbol": r.spread.underlying_symbol,
                "structure_type": r.spread.structure_type,
                "advisory_group": r.advisory_group,
                "reward_risk": r.reward_risk,
                "pmp": r.pmp,
                "expected_value": r.expected_value,
                "spread_delta": r.spread_delta,
                "approved_in_file": r.approved_in_file,
            }
        )
    return out


def evaluate_scenario(
    rows: list[EnrichedSweepRow],
    spec: ScenarioSpec,
) -> ScenarioResult:
    total = len(rows)
    required_rows = [r for r in rows if _rows_with_required_fields(r, requires_bid_ask=spec.requires_bid_ask)]
    survivors = [r for r in required_rows if spec.predicate(r)]
    missing_agg: dict[str, int] = {}
    for r in rows:
        for k, v in _missing_fields(r, requires_bid_ask=spec.requires_bid_ask).items():
            missing_agg[k] = missing_agg.get(k, 0) + v

    by_structure: dict[str, int] = {}
    by_advisory: dict[str, int] = {}
    for r in survivors:
        st = r.spread.structure_type or "UNKNOWN"
        by_structure[st] = by_structure.get(st, 0) + 1
        by_advisory[r.advisory_group] = by_advisory.get(r.advisory_group, 0) + 1

    pass_count = len(survivors)
    req_n = len(required_rows)
    pass_rate = (pass_count / req_n) if req_n else 0.0

    return ScenarioResult(
        scenario_name=spec.name,
        total_input_rows=total,
        rows_with_required_fields=req_n,
        pass_count=pass_count,
        pass_rate=pass_rate,
        candidate_pass_count=sum(1 for r in rows if r.candidate_pass),
        approved_count=sum(1 for r in survivors if r.approved_in_file),
        avg_reward_risk=_finite_mean([r.reward_risk for r in survivors]),
        median_reward_risk=_finite_median([r.reward_risk for r in survivors]),
        avg_pmp=_finite_mean([r.pmp for r in survivors]),
        median_pmp=_finite_median([r.pmp for r in survivors]),
        avg_expected_value=_finite_mean([r.expected_value for r in survivors]),
        median_expected_value=_finite_median([r.expected_value for r in survivors]),
        avg_bid_ask_spread_pct=_finite_mean([r.bid_ask_spread_pct for r in survivors]),
        by_structure=by_structure,
        by_advisory_group=by_advisory,
        missing_field_counts=missing_agg,
        top_10_survivors=_top_survivors(survivors),
    )


def run_threshold_sweep(
    *,
    spreads_path: Path,
    approvals_path: Path | None = None,
    greeks_path: Path | None = None,
    limit: int | None = None,
) -> tuple[list[EnrichedSweepRow], list[ScenarioResult]]:
    rows = enrich_spread_candidates(
        spreads_path,
        greeks_path=greeks_path,
        approvals_path=approvals_path,
        limit=limit,
    )
    results = [evaluate_scenario(rows, spec) for spec in _build_scenarios()]
    return rows, results


def scenario_results_to_dataframe(results: list[ScenarioResult]) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for r in results:
        rec = asdict(r)
        rec["by_structure"] = json.dumps(r.by_structure, sort_keys=True)
        rec["by_advisory_group"] = json.dumps(r.by_advisory_group, sort_keys=True)
        rec["missing_field_counts"] = json.dumps(r.missing_field_counts, sort_keys=True)
        rec["top_10_survivors"] = json.dumps(r.top_10_survivors)
        records.append(rec)
    if not records:
        return pd.DataFrame(columns=[f.name for f in fields(ScenarioResult)])
    return pd.DataFrame(records)


def build_sweep_summary(
    rows: list[EnrichedSweepRow],
    results: list[ScenarioResult],
    *,
    inputs_present: dict[str, bool],
) -> dict[str, Any]:
    by_name = {r.scenario_name: r for r in results}
    return {
        "provenance": PROVENANCE_TAG,
        "total_input_rows": len(rows),
        "baseline_candidate_pass_count": sum(1 for r in rows if r.candidate_pass),
        "inputs_present": inputs_present,
        "scenarios": {r.scenario_name: asdict(r) for r in results},
        "highlights": {
            "rr_gte_2_00": by_name.get("rr_gte_2_00", {}),
            "ev_gte_0_00": by_name.get("ev_gte_0_00", {}),
            "ev_gte_0_and_bid_ask_spread_pct_lte_0_50": by_name.get(
                "ev_gte_0_and_bid_ask_spread_pct_lte_0_50", {}
            ),
            "ev_gte_0_and_rr_gte_2_00": by_name.get("ev_gte_0_and_rr_gte_2_00", {}),
            "ev_gte_0_and_rr_gte_2_00_and_bid_ask_spread_pct_lte_0_50": by_name.get(
                "ev_gte_0_and_rr_gte_2_00_and_bid_ask_spread_pct_lte_0_50", {}
            ),
        },
        "eligible_by_structure": {
            name: r.by_structure for name, r in by_name.items()
        },
        "eligible_by_advisory_group": {
            name: r.by_advisory_group for name, r in by_name.items()
        },
        "canonical_gates_unchanged": True,
        "transport": "none",
    }


def summary_to_json(summary: dict[str, Any]) -> str:
    return json.dumps(summary, indent=2, sort_keys=True, default=str)
