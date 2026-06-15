from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.requests import OptionChainRequest

from qops.bridge.chain_snapshot_models import REQUIRED_CHAIN_COLUMNS


def read_payload_json(path: str | Path) -> list[dict[str, Any]]:
    """Load a C13D ChatGPT payload JSON file (top-level list of candidate objects).

    Args:
        path: Path to exported JSON (same shape as :func:`qops.bridge.export.export_chatgpt_payloads`).

    Returns:
        List of row dicts.

    Raises:
        FileNotFoundError: If ``path`` is missing.
        ValueError: If JSON is not a non-empty list of objects.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"payload json not found: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("payload json must be a list of candidate objects")
    for i, row in enumerate(data):
        if not isinstance(row, dict):
            raise ValueError(f"payload row {i} must be an object, got {type(row).__name__}")
    return data


def extract_unique_symbol_dates(payload: list[dict[str, Any]]) -> list[tuple[str, str, float]]:
    """Extract unique ``(trade_date, symbol, spot_price)`` tuples in first-seen order.

    ``spot_price`` comes from the first payload row for each pair (``price`` field).

    Args:
        payload: Rows containing at least ``symbol``, ``trade_date``, and ``price`` (C13D export).

    Returns:
        Ordered unique triples with ``symbol`` uppercased; ``spot_price`` is ``float(row['price'])``.
    """
    seen: set[tuple[str, str]] = set()
    triples: list[tuple[str, str, float]] = []
    for row in payload:
        symbol = str(row.get("symbol", "")).strip().upper()
        trade_date = str(row.get("trade_date", "")).strip()
        if not symbol or not trade_date:
            continue
        key = (trade_date, symbol)
        if key not in seen:
            seen.add(key)
            raw_price = row.get("price")
            if raw_price is None:
                raise ValueError(f"payload row missing price for {symbol!r} on {trade_date!r}")
            spot_price = float(raw_price)
            triples.append((trade_date, symbol, spot_price))
    return triples


def parse_occ_us_option_contract(contract_symbol: str) -> tuple[str, float, str]:
    """Parse a US equity option OPRA symbol into expiration, strike, and side.

    Expects the standard OCC suffix: ``YYMMDD`` + ``C`` or ``P`` + 8-digit strike
    (strike × 1000, zero-padded).

    Args:
        contract_symbol: Full option symbol (e.g. ``SPY250117C00600000``).

    Returns:
        ``(expiration YYYY-MM-DD, strike, option_type)`` where ``option_type`` is
        ``call`` or ``put``.

    Raises:
        ValueError: If the symbol does not match the expected OCC pattern.
    """
    s = contract_symbol.strip().upper().replace(" ", "")
    if len(s) < 15:
        raise ValueError(f"option contract symbol too short: {contract_symbol!r}")
    strike_raw = s[-8:]
    cp = s[-9]
    date_part = s[-15:-9]
    if cp not in ("C", "P"):
        raise ValueError(f"option contract symbol missing C/P type: {contract_symbol!r}")
    yy = int(date_part[:2])
    month = int(date_part[2:4])
    day = int(date_part[4:6])
    year = 2000 + yy if yy < 70 else 1900 + yy
    expiration = f"{year:04d}-{month:02d}-{day:02d}"
    strike = int(strike_raw) / 1000.0
    option_type = "call" if cp == "C" else "put"
    return expiration, strike, option_type


def rows_from_raw_option_chain(snapshots: dict[str, Any]) -> list[dict[str, Any]]:
    """Build chain rows from Alpaca ``get_option_chain`` raw JSON (``raw_data=True``).

    Alpaca returns a mapping of option contract symbol → snapshot object. Open interest
    appears as ``openInterest`` in API JSON when present; otherwise we use ``0``.

    Args:
        snapshots: Raw mapping from contract symbol to snapshot dict.

    Returns:
        Row dicts with keys ``expiration``, ``strike``, ``option_type``, ``open_interest``.

    Raises:
        ValueError: If ``snapshots`` is not a mapping.
    """
    if not isinstance(snapshots, dict):
        raise ValueError(f"option chain response must be a dict, got {type(snapshots).__name__}")
    rows: list[dict[str, Any]] = []
    for contract_symbol, snap in snapshots.items():
        if not isinstance(snap, dict):
            continue
        oi_raw = snap.get("openInterest", snap.get("open_interest"))
        if oi_raw is None:
            open_interest = 0
        else:
            try:
                open_interest = int(oi_raw)
            except (TypeError, ValueError) as e:
                raise ValueError(f"invalid open interest for {contract_symbol!r}") from e
        try:
            expiration, strike, option_type = parse_occ_us_option_contract(str(contract_symbol))
        except ValueError:
            continue
        rows.append(
            {
                "expiration": expiration,
                "strike": strike,
                "option_type": option_type,
                "open_interest": open_interest,
            }
        )
    return rows


def normalize_chain_df(raw: pd.DataFrame) -> pd.DataFrame:
    """Normalize Alpaca or tabular chain output into the canonical local CSV schema.

    Required output columns: ``expiration``, ``strike``, ``option_type``, ``open_interest``.

    Args:
        raw: DataFrame whose columns may use common aliases.

    Returns:
        Sorted, validated DataFrame with only the required columns.

    Raises:
        ValueError: If required columns are missing after normalization or ``option_type`` is invalid.
    """
    aliases = {
        "expiration_date": "expiration",
        "expiry": "expiration",
        "expiration": "expiration",
        "strike_price": "strike",
        "strike": "strike",
        "type": "option_type",
        "option_type": "option_type",
        "side": "option_type",
        "open_interest": "open_interest",
        "oi": "open_interest",
    }

    rename_map: dict[str, str] = {}
    for col in raw.columns:
        key = str(col).strip().lower()
        if key in aliases:
            rename_map[col] = aliases[key]

    df = raw.rename(columns=rename_map).copy()

    missing = [c for c in REQUIRED_CHAIN_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"missing required chain columns after normalization: {missing}")

    df = df[list(REQUIRED_CHAIN_COLUMNS)].copy()
    df["expiration"] = df["expiration"].astype(str)
    df["strike"] = pd.to_numeric(df["strike"], errors="raise")
    df["option_type"] = (
        df["option_type"].astype(str).str.strip().str.lower().replace({"c": "call", "p": "put"})
    )
    df["open_interest"] = pd.to_numeric(df["open_interest"], errors="coerce").fillna(0).astype(int)

    invalid = ~df["option_type"].isin(["call", "put"])
    if invalid.any():
        bad = sorted(df.loc[invalid, "option_type"].astype(str).unique().tolist())
        raise ValueError(f"invalid option_type values found: {bad}")

    return df.sort_values(["expiration", "strike", "option_type"]).reset_index(drop=True)


def chain_output_path(output_root: str | Path, trade_date: str, symbol: str) -> Path:
    """Return the canonical CSV path ``{output_root}/{trade_date}/{SYMBOL}.csv``."""

    out_dir = Path(output_root) / trade_date
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{symbol.strip().upper()}.csv"


def write_chain_snapshot_csv(df: pd.DataFrame, path: str | Path) -> None:
    """Write a normalized chain DataFrame to CSV (no index).

    Args:
        df: Output of :func:`normalize_chain_df`.
        path: Destination file path.

    Raises:
        ValueError: If required columns are missing.
        OSError: On write failure.
    """
    missing = [c for c in REQUIRED_CHAIN_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"cannot write chain CSV: missing columns {missing}")
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(p, index=False)


def filter_chain_strikes_near_atm(
    df: pd.DataFrame,
    spot_price: float,
    *,
    strikes_each_side: int = 10,
) -> pd.DataFrame:
    """Keep only strikes within ``strikes_each_side`` steps of ATM per expiration.

    ATM is the listed strike closest to ``spot_price``. Strikes are ordered in exchange
    strike space (``unique`` sorted); the window is **±10 strikes** around that index
    (up to ``2 * strikes_each_side + 1`` distinct strikes per expiration).

    Args:
        df: Normalized chain DataFrame (see :func:`normalize_chain_df`).
        spot_price: Underlying reference from the C13D payload (candidate ``price``).
        strikes_each_side: Half-width in strike rungs (default ``10`` → ±10 around ATM).

    Returns:
        Filtered copy; empty if ``df`` is empty.
    """
    if df.empty:
        return df.copy()
    parts: list[pd.DataFrame] = []
    for _, group in df.groupby("expiration", sort=True):
        strikes = sorted(group["strike"].astype(float).unique().tolist())
        if not strikes:
            continue
        atm_idx = min(range(len(strikes)), key=lambda i: abs(strikes[i] - spot_price))
        lo = max(0, atm_idx - strikes_each_side)
        hi = min(len(strikes), atm_idx + strikes_each_side + 1)
        allowed = frozenset(strikes[lo:hi])
        sub = group[group["strike"].astype(float).isin(allowed)]
        parts.append(sub)
    if not parts:
        return pd.DataFrame(columns=list(REQUIRED_CHAIN_COLUMNS))
    return pd.concat(parts, ignore_index=True).sort_values(
        ["expiration", "strike", "option_type"]
    ).reset_index(drop=True)


def payload_date_to_chain_expiration_window(trade_date: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Map a payload ``trade_date`` to an expiration filter window for chain discovery.

    Uses the trade date as the lower bound and a short forward window so the Alpaca
    chain endpoint returns discoverable expirations (research-only; not a forecast).

    Args:
        trade_date: ``YYYY-MM-DD`` string.

    Returns:
        ``(start, end)`` timestamps for filtering contract expirations.
    """
    start = pd.Timestamp(trade_date)
    end = start + pd.Timedelta(days=35)
    return start, end


def fetch_chain_dataframe_for_symbol(
    client: OptionHistoricalDataClient,
    *,
    symbol: str,
    trade_date: str,
    spot_price: float,
    strikes_each_side: int = 10,
) -> pd.DataFrame:
    """Fetch delayed option-chain snapshots for an underlying and return a canonical DataFrame.

    Uses :class:`~alpaca.data.historical.option.OptionHistoricalDataClient` with
    ``raw_data=True`` so open interest and contract symbols match the HTTP API.

    After normalization, rows are restricted to **±``strikes_each_side`` strikes around
    ATM** (strike nearest ``spot_price``) separately for each expiration.

    Args:
        client: Historical options client (must use ``raw_data=True`` for OI fields).
        symbol: Underlying ticker.
        trade_date: Session date from the C13D payload (``YYYY-MM-DD``).
        spot_price: Candidate underlying price from the payload (ATM anchor).
        strikes_each_side: Keep this many strike rungs below and above ATM (default ``10``).

    Returns:
        Normalized, ATM-windowed chain rows, or empty DataFrame if the API returns no contracts.

    Raises:
        ValueError: If the API returns a non-dict body or normalization fails on non-empty data.
    """
    start, end = payload_date_to_chain_expiration_window(trade_date)
    request = OptionChainRequest(
        underlying_symbol=symbol,
        expiration_date_gte=start.date(),
        expiration_date_lte=end.date(),
    )
    raw = client.get_option_chain(request)
    rows = rows_from_raw_option_chain(raw)
    if not rows:
        return pd.DataFrame(columns=list(REQUIRED_CHAIN_COLUMNS))
    df = normalize_chain_df(pd.DataFrame(rows))
    return filter_chain_strikes_near_atm(df, spot_price, strikes_each_side=strikes_each_side)
