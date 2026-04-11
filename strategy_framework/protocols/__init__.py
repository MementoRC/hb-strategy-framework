"""Protocols: pure Protocol contracts for hb-strategy-framework."""

from strategy_framework.protocols.composites import (
    BarrierControlProtocol,
    OrderTrackingProtocol,
    PnLProtocol,
    RetryProtocol,
)
from strategy_framework.protocols.config import ConfigProtocol, UpdatableConfigProtocol
from strategy_framework.protocols.controller import ControllerProtocol
from strategy_framework.protocols.executor import ExecutorProtocol
from strategy_framework.protocols.lifecycle import BarrierProtocol, ShutdownProtocol
from strategy_framework.protocols.market import (
    CancelOrderSignature,
    GetMidPriceSignature,
    MarketAccessProtocol,
    PlaceOrderSignature,
)
from strategy_framework.protocols.order import TrackedOrderProtocol

__all__ = [
    "BarrierControlProtocol",
    "BarrierProtocol",
    "CancelOrderSignature",
    "ConfigProtocol",
    "ControllerProtocol",
    "ExecutorProtocol",
    "GetMidPriceSignature",
    "MarketAccessProtocol",
    "OrderTrackingProtocol",
    "PlaceOrderSignature",
    "PnLProtocol",
    "RetryProtocol",
    "ShutdownProtocol",
    "TrackedOrderProtocol",
    "UpdatableConfigProtocol",
]
