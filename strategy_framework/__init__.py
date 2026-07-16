"""hb-strategy-framework: Strategy composition framework for Hummingbot."""

from strategy_framework.__about__ import __version__

# Building blocks
from strategy_framework.building_blocks.indicators import (
    bollinger_bands,
    macd,
    rsi,
    supertrend,
)

# Config
from strategy_framework.config import StrategyConfigBase

# Executors
from strategy_framework.executors import (
    ExecutorBase,
    ExecutorConfigBase,
    ExecutorState,
    ExecutorStateError,
    TripleBarrierExecutor,
    TripleBarrierExecutorConfig,
)

# Orchestrator
from strategy_framework.hb_compat import EventBusAdapter

# Mixins
from strategy_framework.mixins.executor import (
    ActivationBoundsMixin,
    BalanceValidationMixin,
    OrderTrackingMixin,
    PNLCalculatorMixin,
    RetryMixin,
    ShutdownMixin,
    TrailingStopMixin,
)
from strategy_framework.orchestrator import ExecutorManager, StrategyOrchestrator

# Primitives
from strategy_framework.primitives import (
    CandleData,
    CloseType,
    CreateExecutorAction,
    DataRequirement,
    ExecutorNotification,
    OrderBookEntry,
    OrderBookSnapshot,
    OrderType,
    PercentData,
    RunnableStatus,
    StopExecutorAction,
    TradeType,
    TradingRules,
    TrailingStop,
    TripleBarrierConfig,
    UpdateExecutorAction,
)

# Protocols
from strategy_framework.protocols.composites import (
    ActivationBoundsProtocol,
    BarrierControlProtocol,
    OrderTrackingProtocol,
    PnLHostProtocol,
    PnLProtocol,
    RetryHostProtocol,
    RetryProtocol,
)
from strategy_framework.protocols.config import ConfigProtocol, UpdatableConfigProtocol
from strategy_framework.protocols.controller import ControllerProtocol
from strategy_framework.protocols.event_bus import EventBusProtocol
from strategy_framework.protocols.executor import ExecutorProtocol
from strategy_framework.protocols.market import MarketAccessProtocol
from strategy_framework.protocols.market_data import MarketDataProtocol
from strategy_framework.protocols.orchestrator import OrchestratorProtocol
from strategy_framework.protocols.order import TrackedOrderProtocol
from strategy_framework.protocols.trading_rules import TradingRulesProtocol

__all__ = [
    "__version__",
    # Executors
    "ExecutorBase",
    "ExecutorConfigBase",
    "ExecutorState",
    "ExecutorStateError",
    "TripleBarrierExecutor",
    "TripleBarrierExecutorConfig",
    # Mixins
    "ActivationBoundsMixin",
    "BalanceValidationMixin",
    "OrderTrackingMixin",
    "PNLCalculatorMixin",
    "RetryMixin",
    "ShutdownMixin",
    "TrailingStopMixin",
    # Primitives
    # Orchestrator
    "ExecutorManager",
    "EventBusAdapter",
    "StrategyOrchestrator",
    # Primitives
    "CandleData",
    "CloseType",
    "CreateExecutorAction",
    "DataRequirement",
    "ExecutorNotification",
    "OrderBookEntry",
    "OrderBookSnapshot",
    "OrderType",
    "PercentData",
    "RunnableStatus",
    "StopExecutorAction",
    "TradeType",
    "TradingRules",
    "TrailingStop",
    "TripleBarrierConfig",
    "UpdateExecutorAction",
    # Building blocks
    "bollinger_bands",
    "macd",
    "rsi",
    "supertrend",
    # Protocols
    "ActivationBoundsProtocol",
    "BarrierControlProtocol",
    "ConfigProtocol",
    "ControllerProtocol",
    "ExecutorProtocol",
    "MarketAccessProtocol",
    "MarketDataProtocol",
    "OrderTrackingProtocol",
    "PnLHostProtocol",
    "PnLProtocol",
    "RetryHostProtocol",
    "RetryProtocol",
    "EventBusProtocol",
    "OrchestratorProtocol",
    "TrackedOrderProtocol",
    "TradingRulesProtocol",
    "UpdatableConfigProtocol",
    # Config
    "StrategyConfigBase",
]
