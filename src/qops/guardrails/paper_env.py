"""Paper-only environment guardrails."""

from __future__ import annotations

import os

from qops.guardrails.base import (
    STATUS_LIVE_ENV_FORBIDDEN,
    GuardrailCandidate,
    GuardrailResult,
)


def _live_trade_env_forbidden() -> bool:
    raw = os.environ.get("ALPACA_LIVE_TRADE")
    if raw is None:
        return False
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def check_paper_environment(candidate: GuardrailCandidate) -> GuardrailResult:
    if _live_trade_env_forbidden() or candidate.live_env_hint:
        return GuardrailResult.reject(
            status=STATUS_LIVE_ENV_FORBIDDEN,
            reason_code=STATUS_LIVE_ENV_FORBIDDEN,
            message="live_trading_env_forbidden",
            details={"ALPACA_LIVE_TRADE": os.environ.get("ALPACA_LIVE_TRADE")},
        )
    if not candidate.paper_only:
        return GuardrailResult.reject(
            status=STATUS_LIVE_ENV_FORBIDDEN,
            reason_code=STATUS_LIVE_ENV_FORBIDDEN,
            message="paper_only_required",
            details={"paper_only": candidate.paper_only},
        )
    if not candidate.account_mode_paper:
        return GuardrailResult.reject(
            status=STATUS_LIVE_ENV_FORBIDDEN,
            reason_code=STATUS_LIVE_ENV_FORBIDDEN,
            message="account_mode_not_proven_paper",
            details={"account_mode_paper": candidate.account_mode_paper},
        )
    return GuardrailResult.pass_(message="paper_environment_ok")
