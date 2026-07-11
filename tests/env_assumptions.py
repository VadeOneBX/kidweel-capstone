"""Explicit environment assumptions for unit vs integration tests.

Unit tests must not depend on developer shell credentials or private files.
Integration tests must call require_* helpers so absence yields a clear skip.
"""

from __future__ import annotations

import os

import pytest

ALPACA_PAPER_INTEGRATION_ENV = (
    "ALPACA_PAPER_API_KEY",
    "ALPACA_PAPER_SECRET_KEY",
    "ALPACA_PAPER_BASE_URL",
)

ALPACA_MARKET_DATA_INTEGRATION_ENV = (
    "ALPACA_API_KEY",
    "ALPACA_SECRET_KEY",
)


def require_env_vars(*names: str, reason: str | None = None) -> None:
    """Skip the calling test when required environment variables are absent."""
    missing = [name for name in names if not str(os.environ.get(name) or "").strip()]
    if missing:
        detail = reason or "required integration environment variables are not set"
        pytest.skip(f"{detail}: missing {', '.join(missing)}")


def require_alpaca_paper_integration_env() -> None:
    require_env_vars(
        *ALPACA_PAPER_INTEGRATION_ENV,
        reason="Alpaca paper transport integration requires ALPACA_PAPER_* credentials",
    )


def require_alpaca_market_data_integration_env() -> None:
    require_env_vars(
        *ALPACA_MARKET_DATA_INTEGRATION_ENV,
        reason="Alpaca market-data integration requires ALPACA_API_KEY/ALPACA_SECRET_KEY",
    )
