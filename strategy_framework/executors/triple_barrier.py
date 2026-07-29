"""TripleBarrierExecutorConfig and TripleBarrierExecutor.

Implements a position executor with TP / SL / time-limit / trailing-stop exits.

Mixin initialization:
- OrderTrackingMixin: requires _init_order_tracking() — owns order lists
- TrailingStopMixin: requires _init_trailing_stop() — owns peak_pnl state
- ActivationBoundsMixin: init-free (pure function)
- PNLCalculatorMixin: init-free (all @property, no internal state)
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, override

from strategy_framework.executors.base import ExecutorBase, ExecutorConfigBase, ExecutorState
from strategy_framework.hb_compat import get_logger
from strategy_framework.hb_compat.common import TradeType  # noqa: TC001
from strategy_framework.mixins.executor.activation import ActivationBoundsMixin
from strategy_framework.mixins.executor.order_tracking import OrderTrackingMixin
from strategy_framework.mixins.executor.pnl import PNLCalculatorMixin
from strategy_framework.mixins.executor.trailing_stop import TrailingStopMixin
from strategy_framework.primitives.enums import CloseType
from strategy_framework.primitives.trailing_stop import TrailingStop  # noqa: TC001
from strategy_framework.primitives.triple_barrier import TripleBarrierConfig  # noqa: TC001

if TYPE_CHECKING:
    from strategy_framework.hb_compat import EventBusAdapter
    from strategy_framework.protocols.market import MarketAccessProtocol

logger = get_logger(__name__)


class TripleBarrierExecutorConfig(ExecutorConfigBase):
    trading_pair: str
    side: TradeType
    entry_price: Decimal
    amount: Decimal
    triple_barrier: TripleBarrierConfig
    trailing_stop: TrailingStop | None = None
    activation_bounds: tuple[Decimal, Decimal] | None = None


class TripleBarrierExecutor(
    ActivationBoundsMixin,
    OrderTrackingMixin,
    PNLCalculatorMixin,
    TrailingStopMixin,
    ExecutorBase,
):
    """Executor that closes a position when any triple-barrier condition is met.

    Barriers (checked in order after each event):
    1. Take-profit: trade_pnl_pct >= triple_barrier.take_profit
    2. Stop-loss:   trade_pnl_pct <= -triple_barrier.stop_loss
    3. Time-limit:  elapsed seconds >= triple_barrier.time_limit_s  (checked in tick)
    4. Trailing stop: ratchet algorithm in TrailingStopMixin

    Activation bounds (optional):
    - If configured, executor stays IDLE after start() until price enters bounds.
    - Price updates while IDLE re-check bounds and activate if in range.
    """

    def __init__(
        self,
        market: MarketAccessProtocol,
        config: TripleBarrierExecutorConfig,
        bus: EventBusAdapter | None = None,
    ) -> None:
        super().__init__(market=market, config=config, bus=bus)
        self._config: TripleBarrierExecutorConfig  # narrow type for mypy
        # PNL host state
        self._entry_price_filled: Decimal = Decimal("0")
        self._close_price: Decimal = Decimal("0")
        self._open_filled_amount: Decimal = Decimal("0")  # base amount filled on entry
        self._cum_fees: Decimal = Decimal("0")
        # Fill-phase tracking: first fill → entry, subsequent → close
        self._entry_filled: bool = False
        # Started-at for time-limit
        self._started_at: datetime.datetime | None = None
        # Mixin init
        self._init_order_tracking()  # type: ignore[misc]
        self._init_trailing_stop()  # type: ignore[misc]

    # ------------------------------------------------------------------
    # ActivationBoundsProtocol properties (read from config)
    # ------------------------------------------------------------------

    @property
    def entry_price(self) -> Decimal:
        """Config entry price (used by ActivationBoundsMixin and PNLCalculatorMixin)."""
        return self._config.entry_price

    @property
    def activation_bounds(self) -> tuple[Decimal, Decimal] | None:
        return self._config.activation_bounds

    # ------------------------------------------------------------------
    # PnLHostProtocol properties
    # ------------------------------------------------------------------

    @property
    def close_price(self) -> Decimal:
        """Most recent close price (updated by price events and close fills)."""
        return self._close_price

    @property
    def open_filled_amount_quote(self) -> Decimal:
        """Entry fill value in quote (filled_amount * entry_fill_price)."""
        return self._open_filled_amount * self._entry_price_filled

    @property
    def trade_side(self) -> TradeType:
        return self._config.side

    @property
    def cum_fees_raw(self) -> Decimal:
        return self._cum_fees

    # ------------------------------------------------------------------
    # BarrierControlProtocol properties (for TrailingStopMixin)
    # ------------------------------------------------------------------

    @property
    def triple_barrier(self) -> TripleBarrierConfig:
        return self._config.triple_barrier

    @property
    def trailing_stop(self) -> TrailingStop | None:
        return self._config.trailing_stop

    @property
    def elapsed_seconds(self) -> float:
        if self._started_at is None:
            return 0.0
        now = datetime.datetime.now(datetime.UTC)
        return (now - self._started_at).total_seconds()

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    @override
    def on_started(self) -> None:
        """Called after IDLE→ACTIVE transition.

        If outside activation bounds, revert to IDLE (no entry order placed).
        Otherwise set started_at and place the entry order.
        """
        mid = self._market.get_mid_price()
        if not self.is_within_activation_bounds(mid):  # type: ignore[misc]
            # Revert state — executor will activate on a future price update
            self._state = ExecutorState.IDLE
            return
        self._started_at = datetime.datetime.now(datetime.UTC)
        self._close_price = self._config.entry_price  # initial close = entry target
        self._place_entry_order()

    @override
    def on_price_updated(self, price: Decimal) -> None:
        """Handle price tick.

        - IDLE: re-check activation bounds; activate if now in range.
        - ACTIVE: update close price, check trailing stop.
        """
        if self._state == ExecutorState.IDLE:
            if self.is_within_activation_bounds(price):  # type: ignore[misc]
                self._state = ExecutorState.ACTIVE
                self._started_at = datetime.datetime.now(datetime.UTC)
                self._close_price = self._config.entry_price
                self._place_entry_order()
            return

        if self._state != ExecutorState.ACTIVE:
            return

        # Update close price to current mid for PnL calculation
        if self._entry_filled:
            self._close_price = price
            self.update_trailing_stop(price)  # type: ignore[misc]
            if self.trailing_stop_triggered:  # type: ignore[misc]
                self.stop(CloseType.TRAILING_STOP)

    @override
    def on_order_filled(self, order_id: str, price: Decimal, amount: Decimal) -> None:
        """Track order fills; check barriers after each fill."""
        if not self._entry_filled:
            # First fill is the entry fill
            self._entry_price_filled = price
            self._open_filled_amount += amount
            self._close_price = price
            self._entry_filled = True
        else:
            # Subsequent fills are close fills
            self._close_price = price
            self._check_barriers()

    @override
    def on_order_failed(self, order_id: str, reason: str) -> None:
        logger.warning("Order %s failed: %s", order_id, reason)
        self.stop(CloseType.FAILED)

    @override
    def on_stopped(self, close_type: CloseType) -> None:
        """Cancel all tracked open orders on close."""
        for order in list(self._open_orders):
            self._market.cancel_order(order.order_id)

    # ------------------------------------------------------------------
    # Time-limit tick
    # ------------------------------------------------------------------

    @override
    def tick(self, now: datetime.datetime) -> None:
        """Check time-limit barrier. Called by Controller heartbeat or tests."""
        if self._state != ExecutorState.ACTIVE:
            return
        tb = self.triple_barrier
        if not tb.has_time_limit:
            return
        if self._started_at is None:
            return
        elapsed = (now - self._started_at).total_seconds()
        if elapsed >= tb.time_limit_s:
            self.stop(CloseType.TIME_LIMIT)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _place_entry_order(self) -> str:
        """Place the entry limit order and track it."""
        from strategy_framework.testing.factories import (
            TrackedOrderFactory,
        )  # TODO(plan4): replace with primitives.TrackedOrder

        order_id = self._market.place_order(
            order_type="limit",
            side=self._config.side.value,
            amount=self._config.amount,
            price=self._config.entry_price,
        )
        tracked = TrackedOrderFactory.open_order(
            order_id=order_id,
            amount=self._config.amount,
            price=self._config.entry_price,
            side=self._config.side.value,
        )
        self.add_open_order(tracked)  # type: ignore[misc]
        return order_id

    def _check_barriers(self) -> None:
        """Evaluate TP and SL thresholds after a close fill."""
        if self._state != ExecutorState.ACTIVE:
            return
        tb = self.triple_barrier
        pnl = self.trade_pnl_pct

        if tb.has_take_profit and pnl >= tb.take_profit:
            self.stop(CloseType.TAKE_PROFIT)
            return

        if tb.has_stop_loss and pnl <= -tb.stop_loss:
            self.stop(CloseType.STOP_LOSS)
            return
