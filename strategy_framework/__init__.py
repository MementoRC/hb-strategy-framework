"""hb-strategy-framework: Strategy composition framework for Hummingbot."""

from strategy_framework.__about__ import __version__

# Config
from strategy_framework.config import StrategyConfigBase

# Primitives
from strategy_framework.primitives import (
    CloseType,
    CreateExecutorAction,
    OrderType,
    PercentData,
    RunnableStatus,
    StopExecutorAction,
    TradeType,
    TrailingStop,
    TripleBarrierConfig,
    UpdateExecutorAction,
)

# Protocols
from strategy_framework.protocols.composites import BarrierControlProtocol, PnLProtocol
from strategy_framework.protocols.config import ConfigProtocol, UpdatableConfigProtocol
from strategy_framework.protocols.controller import ControllerProtocol
from strategy_framework.protocols.executor import ExecutorProtocol
from strategy_framework.protocols.market import MarketAccessProtocol
from strategy_framework.protocols.order import TrackedOrderProtocol

__all__ = [
    "__version__",
    # Primitives
    "CloseType",
    "CreateExecutorAction",
    "OrderType",
    "PercentData",
    "RunnableStatus",
    "StopExecutorAction",
    "TradeType",
    "TrailingStop",
    "TripleBarrierConfig",
    "UpdateExecutorAction",
    # Protocols
    "BarrierControlProtocol",
    "ConfigProtocol",
    "ControllerProtocol",
    "ExecutorProtocol",
    "MarketAccessProtocol",
    "PnLProtocol",
    "TrackedOrderProtocol",
    "UpdatableConfigProtocol",
    # Config
    "StrategyConfigBase",
]
