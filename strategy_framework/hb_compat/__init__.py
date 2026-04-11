"""Hummingbot compatibility layer.

Provides the bridge between the standalone strategy framework and
the Hummingbot trading platform, translating between internal domain
models and Hummingbot's expected interfaces.
"""

from strategy_framework.hb_compat.data_types import StrategyConfig
from strategy_framework.hb_compat.protocols import StrategyBaseProtocol

__all__ = [
    "StrategyBaseProtocol",
    "StrategyConfig",
]
