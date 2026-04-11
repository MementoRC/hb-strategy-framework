"""Hummingbot-compatible data types.

Pydantic models matching Hummingbot's configuration and data
structures for strategy components.
"""

from __future__ import annotations

from pydantic import BaseModel


class StrategyConfig(BaseModel):
    """Configuration for a strategy instance.

    Mirrors the configuration structure expected by Hummingbot's
    strategy loader.
    """

    strategy_name: str
    trading_pair: str
    exchange: str


class UnsupportedStrategyError(Exception):
    """Raised when a requested strategy type is not supported."""
