"""Protocols: pure Protocol contracts for hb-strategy-framework."""

from strategy_framework.protocols.composites import (
    BarrierControlProtocol,
    OrderTrackingProtocol,
    PnLProtocol,
    RetryProtocol,
)
from strategy_framework.protocols.config import ConfigProtocol, UpdatableConfigProtocol
from strategy_framework.protocols.controller import ControllerProtocol
from strategy_framework.protocols.event_bus import EventBusProtocol
from strategy_framework.protocols.executor import ExecutorProtocol
from strategy_framework.protocols.lifecycle import (
    BarrierProtocol,
    ShutdownProtocol,
)
from strategy_framework.protocols.market import (
    CancelOrderSignature,
    GetMidPriceSignature,
    MarketAccessProtocol,
    PlaceOrderSignature,
)
from strategy_framework.protocols.market_data import MarketDataProtocol
from strategy_framework.protocols.orchestrator import OrchestratorProtocol
from strategy_framework.protocols.order import TrackedOrderProtocol
from strategy_framework.protocols.trading_rules import TradingRulesProtocol

__all__ = [
    "BarrierControlProtocol",
    "BarrierProtocol",
    "CancelOrderSignature",
    "ConfigProtocol",
    "ControllerProtocol",
    "EventBusProtocol",
    "ExecutorProtocol",
    "GetMidPriceSignature",
    "MarketAccessProtocol",
    "OrderTrackingProtocol",
    "OrchestratorProtocol",
    "PlaceOrderSignature",
    "PnLProtocol",
    "RetryProtocol",
    "ShutdownProtocol",
    "MarketDataProtocol",
    "TrackedOrderProtocol",
    "TradingRulesProtocol",
    "UpdatableConfigProtocol",
]
