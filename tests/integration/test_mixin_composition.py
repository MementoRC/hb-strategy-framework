"""Integration tests for mixin composition.

Tests verify:
1. MRO-safe _init_*() call order
2. State isolation between mixins
3. PNLCalculatorMixin + TrailingStopMixin real-world composition
"""

from __future__ import annotations

from decimal import Decimal

from strategy_framework.mixins.executor import (
    OrderTrackingMixin,
    PNLCalculatorMixin,
    RetryMixin,
    TrailingStopMixin,
)
from strategy_framework.primitives.enums import CloseType, RunnableStatus, TradeType
from strategy_framework.primitives.trailing_stop import TrailingStop
from strategy_framework.primitives.triple_barrier import TripleBarrierConfig
from strategy_framework.testing.factories import TrackedOrderFactory


# ---------------------------------------------------------------------------
# Composite 1: Retry + OrderTracking + TrailingStop
# ---------------------------------------------------------------------------


class MultiMixinExecutor(RetryMixin, OrderTrackingMixin, TrailingStopMixin):
    """Combines three mixins — verifies MRO and state isolation."""

    max_retries: int = 3
    close_type: CloseType | None = None
    status = RunnableStatus.RUNNING
    elapsed_seconds: float = 0.0

    def __init__(self, pnl_pct: Decimal = Decimal("0")) -> None:
        self._pnl_pct = pnl_pct
        self._init_retry()
        self._init_order_tracking()
        self._init_trailing_stop()

    @property
    def net_pnl_pct(self) -> Decimal:
        return self._pnl_pct

    @property
    def trailing_stop(self) -> TrailingStop | None:
        return TrailingStop(
            activation_price_pct=Decimal("0.02"),
            trailing_delta_pct=Decimal("0.01"),
        )

    @property
    def triple_barrier(self) -> TripleBarrierConfig:
        return TripleBarrierConfig(stop_loss=Decimal("0.05"), take_profit=Decimal("0.1"))

    def place_close_order(self, close_type: CloseType) -> None:
        self.close_type = close_type


def test_all_mixins_initialize() -> None:
    obj = MultiMixinExecutor()
    assert obj.current_retries == 0
    assert obj.open_orders == []
    assert obj.trailing_stop_activated is False


def test_retry_state_independent_of_order_tracking() -> None:
    obj = MultiMixinExecutor()
    obj.increment_retries()
    obj.add_open_order(TrackedOrderFactory.open_order())
    assert obj.current_retries == 1
    assert len(obj.open_orders) == 1


def test_order_tracking_unaffected_by_retry_reset() -> None:
    obj = MultiMixinExecutor()
    obj.add_open_order(TrackedOrderFactory.open_order(order_id="o1"))
    obj.increment_retries()
    obj._init_retry()  # reset retry state only
    assert len(obj.open_orders) == 1  # order tracking unaffected
    assert obj.current_retries == 0


def test_double_init_resets_all_state() -> None:
    obj = MultiMixinExecutor()
    obj.increment_retries()
    obj.add_open_order(TrackedOrderFactory.open_order())
    obj._init_retry()
    obj._init_order_tracking()
    obj._init_trailing_stop()
    assert obj.current_retries == 0
    assert obj.open_orders == []
    assert obj.trailing_stop_activated is False


# ---------------------------------------------------------------------------
# Composite 2: PNLCalculatorMixin + TrailingStopMixin
# (trailing stop reads net_pnl_pct from PNLCalculatorMixin)
# ---------------------------------------------------------------------------


class PnLTrailingExecutor(PNLCalculatorMixin, TrailingStopMixin):
    """Key real-world composition: trailing stop fires when PnL drops enough."""

    close_type: CloseType | None = None
    status = RunnableStatus.RUNNING
    elapsed_seconds: float = 0.0

    def __init__(
        self,
        entry: str,
        close: str,
        filled_quote: str,
        side: TradeType = TradeType.BUY,
        fees: str = "0",
    ) -> None:
        self._entry = Decimal(entry)
        self._close = Decimal(close)
        self._filled_quote = Decimal(filled_quote)
        self._side = side
        self._fees = Decimal(fees)
        self._init_trailing_stop()

    @property
    def entry_price(self) -> Decimal:
        return self._entry

    @property
    def close_price(self) -> Decimal:
        return self._close

    @property
    def open_filled_amount_quote(self) -> Decimal:
        return self._filled_quote

    @property
    def trade_side(self) -> TradeType:
        return self._side

    @property
    def cum_fees_raw(self) -> Decimal:
        return self._fees

    @property
    def trailing_stop(self) -> TrailingStop | None:
        return TrailingStop(
            activation_price_pct=Decimal("0.05"),
            trailing_delta_pct=Decimal("0.02"),
        )

    @property
    def triple_barrier(self) -> TripleBarrierConfig:
        return TripleBarrierConfig(stop_loss=Decimal("0.1"), take_profit=Decimal("0.2"))

    def place_close_order(self, close_type: CloseType) -> None:
        self.close_type = close_type


def test_pnl_trailing_stop_activates_at_threshold() -> None:
    # BUY at 100, close=105 → pnl_pct=0.05 (at activation threshold)
    obj = PnLTrailingExecutor("100", "105", "1000")
    obj.update_trailing_stop(Decimal("105"))
    assert obj.trailing_stop_activated is True


def test_pnl_trailing_stop_not_triggered_at_activation() -> None:
    obj = PnLTrailingExecutor("100", "105", "1000")
    obj.update_trailing_stop(Decimal("105"))
    assert obj.trailing_stop_triggered is False


def test_pnl_trailing_stop_triggered_after_reversal() -> None:
    # Activates at +5%, rises to +8%, then reverses to +5.5% (below trigger of 6%)
    obj = PnLTrailingExecutor("100", "108", "1000")  # pnl=+8%
    obj.update_trailing_stop(Decimal("108"))          # activates; trigger=6%
    obj._close = Decimal("105.5")                     # pnl drops to ~5.5%
    obj.update_trailing_stop(Decimal("105.5"))        # 5.5% < 6% trigger → fires
    assert obj.trailing_stop_triggered is True
