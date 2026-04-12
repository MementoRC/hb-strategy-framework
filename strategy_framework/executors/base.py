from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

from strategy_framework.config.base import StrategyConfigBase
from strategy_framework.executors.events import (
    EventBus,
    OrderCancelledEvent,
    OrderFailedEvent,
    OrderFilledEvent,
    PriceUpdatedEvent,
)

if TYPE_CHECKING:
    import datetime
    from decimal import Decimal

    from strategy_framework.primitives.enums import CloseType
    from strategy_framework.protocols.market import MarketAccessProtocol


class ExecutorState(Enum):
    IDLE = auto()
    ACTIVE = auto()
    CLOSING = auto()
    CLOSED = auto()


class ExecutorStateError(Exception):
    """Raised on invalid state transition."""


class ExecutorConfigBase(StrategyConfigBase):
    """Base config for all executor types."""

    controller_id: str = ""
    controller_name: str = ""
    controller_type: str = "executor"


_VALID_TRANSITIONS: frozenset[tuple[ExecutorState, ExecutorState]] = frozenset(
    {
        (ExecutorState.IDLE, ExecutorState.ACTIVE),
        (ExecutorState.ACTIVE, ExecutorState.CLOSING),
        (ExecutorState.CLOSING, ExecutorState.CLOSED),
    }
)


class ExecutorBase:
    def __init__(
        self,
        market: MarketAccessProtocol,
        config: ExecutorConfigBase,
        bus: EventBus | None = None,
    ) -> None:
        self._market = market
        self._config = config
        self._state = ExecutorState.IDLE
        self.bus: EventBus = bus if bus is not None else EventBus()

    @property
    def state(self) -> ExecutorState:
        return self._state

    def _transition(self, target: ExecutorState) -> None:
        if (self._state, target) not in _VALID_TRANSITIONS:
            raise ExecutorStateError(f"Invalid transition: {self._state.name} → {target.name}")
        self._state = target

    # ------------------------------------------------------------------ #
    # Public lifecycle                                                      #
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        self._transition(ExecutorState.ACTIVE)
        self.on_started()

    def stop(self, close_type: CloseType) -> None:
        if self._state == ExecutorState.CLOSED:
            return  # double-stop guard
        self._transition(ExecutorState.CLOSING)
        self._transition(ExecutorState.CLOSED)
        self.on_stopped(close_type)

    def tick(self, now: datetime.datetime) -> None:
        """Drive time-based checks. Call from on_price_updated or Controller heartbeat."""

    # ------------------------------------------------------------------ #
    # Notify methods — called by external driver (Controller / test)       #
    # ------------------------------------------------------------------ #

    def notify_order_filled(self, order_id: str, price: Decimal, amount: Decimal) -> None:
        self.on_order_filled(order_id, price, amount)
        self.bus.emit("order.filled", OrderFilledEvent(order_id, price, amount))

    def notify_order_cancelled(self, order_id: str) -> None:
        self.on_order_cancelled(order_id)
        self.bus.emit("order.cancelled", OrderCancelledEvent(order_id))

    def notify_order_failed(self, order_id: str, reason: str) -> None:
        self.on_order_failed(order_id, reason)
        self.bus.emit("order.failed", OrderFailedEvent(order_id, reason))

    def notify_price_updated(self, price: Decimal) -> None:
        self.on_price_updated(price)
        self.bus.emit("price.updated", PriceUpdatedEvent(price))

    # ------------------------------------------------------------------ #
    # Dedicated event hooks — override in subclasses                       #
    # ------------------------------------------------------------------ #

    def on_started(self) -> None:
        pass

    def on_stopped(self, close_type: CloseType) -> None:
        pass

    def on_order_filled(self, order_id: str, price: Decimal, amount: Decimal) -> None:
        pass

    def on_order_cancelled(self, order_id: str) -> None:
        pass

    def on_order_failed(self, order_id: str, reason: str) -> None:
        pass

    def on_price_updated(self, price: Decimal) -> None:
        pass
