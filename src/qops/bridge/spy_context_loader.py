from __future__ import annotations

from pathlib import Path

import pandas as pd

from qops.context.spy_store import infer_spy_gamma_regime


def _normalize_trade_date_str(value: object) -> str:
    return pd.to_datetime(value).strftime("%Y-%m-%d")


def _as_bool(value: object) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "t", "yes")
    return bool(value)


def load_spy_context_csv(path: str | Path) -> pd.DataFrame:
    """Load SPY backdrop CSV and normalize to columns expected by the bridge.

    Accepts either:

    - **Market context store** shape: ``trade_date``, ``close``, ``vol_trigger``,
      optional ``gamma_regime``, ``above_vol_trigger`` (and other columns ignored).
    - **Raw SPY history** (SpotGamma export): ``Trade Date``, ``Previous Close``,
      ``Hedge Wall`` — same semantics as ``qops.context.run_spy_store``.

    Args:
        path: Path to a CSV file.

    Returns:
        DataFrame with at least ``trade_date``, ``close``, ``vol_trigger``,
        ``gamma_regime``, ``above_vol_trigger`` for merge logic.

    Raises:
        FileNotFoundError: If ``path`` is missing.
        ValueError: If the schema is not recognized.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"spy context csv not found: {p}")

    raw = pd.read_csv(p)
    if raw.empty:
        return pd.DataFrame(
            columns=[
                "trade_date",
                "close",
                "vol_trigger",
                "gamma_regime",
                "above_vol_trigger",
            ]
        )

    cols = {c.lower(): c for c in raw.columns}

    if "trade_date" in cols and "close" in cols:
        tcol = cols["trade_date"]
        ccol = cols["close"]
        out = raw[[tcol, ccol]].copy()
        out.columns = ["trade_date", "close"]
        out["trade_date"] = out["trade_date"].map(_normalize_trade_date_str)

        vcol = cols.get("vol_trigger")
        if vcol:
            out["vol_trigger"] = raw[vcol].apply(
                lambda x: None if x is None or pd.isna(x) else float(x)
            )
        else:
            out["vol_trigger"] = pd.Series([None] * len(out), index=out.index, dtype=object)

        if "gamma_regime" in cols and "above_vol_trigger" in cols:
            out["gamma_regime"] = raw[cols["gamma_regime"]]
            out["above_vol_trigger"] = raw[cols["above_vol_trigger"]].map(_as_bool)
        else:
            out["gamma_regime"] = [
                infer_spy_gamma_regime(
                    close=float(c),
                    vol_trigger=(
                        None
                        if v is None or (isinstance(v, float) and pd.isna(v))
                        else float(v)
                    ),
                )
                for c, v in zip(out["close"], out["vol_trigger"], strict=True)
            ]
            out["above_vol_trigger"] = [
                vt is not None and not pd.isna(vt) and float(cl) > float(vt)
                for cl, vt in zip(out["close"], out["vol_trigger"], strict=True)
            ]

        return out

    if "trade date" in {c.lower() for c in raw.columns}:
        tcol = next(c for c in raw.columns if c.lower() == "trade date")
        pcol = next(
            (c for c in raw.columns if c.lower() in ("previous close", "close")),
            None,
        )
        hcol = next(
            (c for c in raw.columns if c.lower() == "hedge wall"),
            None,
        )
        if pcol is None:
            raise ValueError(
                "raw SPY history requires 'Previous Close' or 'close' column"
            )
        if hcol is None:
            raise ValueError("raw SPY history requires 'Hedge Wall' or use store CSV")

        rows: list[dict[str, object]] = []
        for _, row in raw.iterrows():
            trade_date = _normalize_trade_date_str(row[tcol])
            close = float(row[pcol])
            vraw = row[hcol]
            vol_trigger = (
                None
                if vraw is None or (isinstance(vraw, float) and pd.isna(vraw))
                else float(vraw)
            )
            gamma_regime = infer_spy_gamma_regime(close=close, vol_trigger=vol_trigger)
            above = vol_trigger is not None and close > vol_trigger
            rows.append(
                {
                    "trade_date": trade_date,
                    "close": close,
                    "vol_trigger": vol_trigger,
                    "gamma_regime": gamma_regime,
                    "above_vol_trigger": above,
                }
            )
        return pd.DataFrame(rows)

    raise ValueError(
        "unrecognized spy context CSV: need (trade_date, close[, vol_trigger]) "
        "or (Trade Date, Previous Close, Hedge Wall)"
    )
