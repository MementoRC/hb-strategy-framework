"""hb-strategy-framework: Strategy composition framework for Hummingbot."""

from strategy_framework.__about__ import __version__

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
from strategy_framework.protocols.executor import ExecutorProtocol
from strategy_framework.protocols.market import MarketAccessProtocol
from strategy_framework.protocols.order import TrackedOrderProtocol

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
    "ActivationBoundsProtocol",
    "BarrierControlProtocol",
    "ConfigProtocol",
    "ControllerProtocol",
    "ExecutorProtocol",
    "MarketAccessProtocol",
    "OrderTrackingProtocol",
    "PnLHostProtocol",
    "PnLProtocol",
    "RetryHostProtocol",
    "RetryProtocol",
    "TrackedOrderProtocol",
    "UpdatableConfigProtocol",
    # Config
    "StrategyConfigBase",
]
