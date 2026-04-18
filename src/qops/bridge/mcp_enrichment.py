from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pandas as pd

from qops.bridge.models import ChatGptCandidatePayload, CandidateFlags, McpChainEnrichmentStats
from qops.context.mcp_chain_summary import summarize_delayed_chain
from qops.context.models import MpcChainSummary

_REQUIRED_PAYLOAD_KEYS = frozenset(
    {
        "symbol",
        "trade_date",
        "source_type",
        "price",
        "vol_trigger",
        "call_wall",
        "put_wall",
        "gamma_ratio",
        "vrp",
        "vrp_z",
        "iv_rank",
        "regime_label",
        "confidence",
        "notes",
        "flags",
        "market_context",
        "chain_context",
    }
)


def chain_snapshot_path_for_symbol(chain_dir: Path, symbol: str) -> Path:
    """Return the expected delayed-chain CSV path for ``symbol``.

    One file per symbol: ``{chain_dir}/{symbol}.csv`` (symbol must match the
    payload ticker exactly, including case).

    Args:
        chain_dir: Directory containing MCP-fed snapshot CSVs.
        symbol: Ticker as it appears on the candidate row.

    Returns:
        Resolved path (file may or may not exist).
    """
    return chain_dir / f"{symbol}.csv"


def mpc_chain_summary_to_chain_context(summary: MpcChainSummary) -> dict:
    """Map a delayed-chain summary into the C13D ``chain_context`` field shape.

    Args:
        summary: Output of :func:`qops.context.mcp_chain_summary.summarize_delayed_chain`.

    Returns:
        Dict with keys matching the C13D stub (no ``note`` field).
    """
    return {
        "nearest_expiration": summary.nearest_expiration,
        "highest_oi_strike": summary.highest_oi_strike,
        "total_call_oi": summary.total_call_oi,
        "total_put_oi": summary.total_put_oi,
        "dominant_side": summary.dominant_side,
        "concentration_near_spot": summary.concentration_near_spot,
        "movement_bias": summary.movement_bias,
    }


def chatgpt_payload_from_dict(obj: dict) -> ChatGptCandidatePayload:
    """Deserialize one ChatGPT bridge row from JSON-compatible dict data.

    Args:
        obj: One mapping with the same keys as :class:`ChatGptCandidatePayload`.

    Returns:
        Parsed payload.

    Raises:
        ValueError: If required keys are missing or types are invalid.
    """
    missing = _REQUIRED_PAYLOAD_KEYS - frozenset(obj.keys())
    if missing:
        raise ValueError(f"ChatGPT payload row missing keys: {sorted(missing)}")

    f = obj["flags"]
    required_flags = (
        "near_call_wall",
        "near_put_wall",
        "inverted_wall",
        "vol_trigger_breach",
        "cross_file_overlap",
    )
    mf = [k for k in required_flags if k not in f]
    if mf:
        raise ValueError(f"ChatGPT payload flags missing keys: {mf}")

    notes = obj["notes"]
    if not isinstance(notes, list):
        raise ValueError("ChatGPT payload 'notes' must be a list of strings")

    return ChatGptCandidatePayload(
        symbol=str(obj["symbol"]),
        trade_date=str(obj["trade_date"]),
        source_type=str(obj["source_type"]),
        price=float(obj["price"]),
        vol_trigger=None if obj["vol_trigger"] is None else float(obj["vol_trigger"]),
        call_wall=None if obj["call_wall"] is None else float(obj["call_wall"]),
        put_wall=None if obj["put_wall"] is None else float(obj["put_wall"]),
        gamma_ratio=None if obj["gamma_ratio"] is None else float(obj["gamma_ratio"]),
        vrp=None if obj["vrp"] is None else float(obj["vrp"]),
        vrp_z=None if obj["vrp_z"] is None else float(obj["vrp_z"]),
        iv_rank=None if obj["iv_rank"] is None else float(obj["iv_rank"]),
        regime_label=None if obj["regime_label"] is None else str(obj["regime_label"]),
        confidence=obj["confidence"],
        notes=tuple(str(x) for x in notes),
        flags=CandidateFlags(
            near_call_wall=bool(f["near_call_wall"]),
            near_put_wall=bool(f["near_put_wall"]),
            inverted_wall=bool(f["inverted_wall"]),
            vol_trigger_breach=bool(f["vol_trigger_breach"]),
            cross_file_overlap=bool(f["cross_file_overlap"]),
        ),
        market_context=dict(obj["market_context"]),
        chain_context=dict(obj["chain_context"]),
    )


def load_chatgpt_payload_json(path: Path) -> list[ChatGptCandidatePayload]:
    """Load a C13D ChatGPT payload JSON file (list of candidate rows).

    Args:
        path: Path to ``chatgpt_payload_*.json``.

    Returns:
        Parsed payloads in file order.

    Raises:
        ValueError: If the file is not a JSON list of objects.
        FileNotFoundError: If ``path`` does not exist.
    """
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError(f"expected JSON array at top level, got {type(data).__name__}")
    return [chatgpt_payload_from_dict(row) for row in data]


def enrich_chatgpt_payloads(
    payloads: list[ChatGptCandidatePayload],
    *,
    chain_dir: Path,
) -> tuple[list[ChatGptCandidatePayload], McpChainEnrichmentStats]:
    """Fill ``chain_context`` from local delayed-chain CSV snapshots where present.

    Uses the same summarization as C13C (:func:`qops.context.mcp_chain_summary.summarize_delayed_chain`).
    Spot ``price`` from each candidate is passed for concentration near spot (±5% band).

    If ``chain_snapshot_path_for_symbol`` does not exist, the row keeps its existing
    ``chain_context`` and counts as skipped.

    Args:
        payloads: Rows from C13D (typically ``chain_context`` stubs).
        chain_dir: Directory of per-symbol CSVs ``{{symbol}}.csv``.

    Returns:
        New payload list with ``chain_context`` updated where snapshots exist, and
        enrichment statistics.

    Raises:
        ValueError: If a snapshot file exists but is empty or fails validation.
    """
    if not chain_dir.is_dir():
        raise ValueError(f"chain_dir is not a directory or does not exist: {chain_dir}")

    out: list[ChatGptCandidatePayload] = []
    enriched = 0
    skipped = 0

    for p in payloads:
        snap = chain_snapshot_path_for_symbol(chain_dir, p.symbol)
        if not snap.is_file():
            out.append(p)
            skipped += 1
            continue

        df_chain = pd.read_csv(snap)
        summary = summarize_delayed_chain(df_chain, symbol=p.symbol, spot_price=p.price)
        new_ctx = mpc_chain_summary_to_chain_context(summary)
        out.append(replace(p, chain_context=new_ctx))
        enriched += 1

    stats = McpChainEnrichmentStats(
        payload_count=len(payloads),
        enriched_count=enriched,
        skipped_count=skipped,
    )
    return out, stats
