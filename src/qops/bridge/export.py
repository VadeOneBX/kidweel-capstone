from __future__ import annotations

import json
import math
from dataclasses import asdict
from pathlib import Path
from typing import Any

from qops.bridge.models import ChatGptCandidatePayload


def _json_safe(value: Any) -> Any:
    """Recursively convert values so ``json.dumps`` emits valid JSON."""
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if hasattr(value, "item"):
        try:
            return _json_safe(value.item())
        except Exception:
            return value
    return value


def export_chatgpt_payloads(
    payloads: list[ChatGptCandidatePayload],
    *,
    output_dir: str | Path,
) -> Path:
    """Write ChatGPT bridge payloads to JSON under ``output_dir``.

    Single ``trade_date`` → ``chatgpt_payload_YYYYMMDD.json``.
    Multiple dates → ``chatgpt_payload_multi_session.json``.

    Args:
        payloads: Serialized candidate payloads.
        output_dir: Directory for output (created if missing).

    Returns:
        Path to the written JSON file.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    dates = sorted({p.trade_date for p in payloads})
    if len(dates) == 1:
        filename = f"chatgpt_payload_{dates[0].replace('-', '')}.json"
    else:
        filename = "chatgpt_payload_multi_session.json"

    path = out / filename
    serialized = [_json_safe(asdict(p)) for p in payloads]
    path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")
    return path
