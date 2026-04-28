from __future__ import annotations

import datetime
from decimal import Decimal

from strategy_framework.executors.base import ExecutorState
from strategy_framework.executors.triple_barrier import (
    TripleBarrierExecutor,
    TripleBarrierExecutorConfig,
)
from strategy_framework.primitives.enums import TradeType
from strategy_framework.primitives.trailing_stop import TrailingStop
from strategy_framework.primitives.triple_barrier import TripleBarrierConfig
from strategy_framework.testing.mock_market import MockMarketAccess


def _make(
    entry_price: Decimal = Decimal("100"),
    stop_loss: Decimal = Decimal("0.02"),
    take_profit: Decimal = Decimal("0.05"),
    time_limit_s: int = 3600,
    trailing_stop: TrailingStop | None = None,
) -> tuple[TripleBarrierExecutor, MockMarketAccess]:
    market = MockMarketAccess()
    market.set_mid_price(entry_price)
    config = TripleBarrierExecutorConfig(
        trading_pair="BTC-USDT",
        side=TradeType.BUY,
        entry_price=entry_price,
        amount=Decimal("1"),
        triple_barrier=TripleBarrierConfig(
            stop_loss=stop_loss,
            take_profit=take_profit,
            time_limit_s=time_limit_s,
        ),
        trailing_stop=trailing_stop,
    )
    return TripleBarrierExecutor(market=market, config=config), market


class TestFullLifecycle:
    def test_happy_path_take_profit(self) -> None:
        ex, market = _make(entry_price=Decimal("100"), take_profit=Decimal("0.05"))
        assert ex.state == ExecutorState.IDLE
        ex.start()
        assert ex.state == ExecutorState.ACTIVE
        ex.notify_order_filled("o1", Decimal("100"), Decimal("1"))
        ex.notify_order_filled("o2", Decimal("106"), Decimal("1"))  # +6% > TP
        assert ex.state == ExecutorState.CLOSED

    def test_stop_loss_path(self) -> None:
        ex, market = _make(entry_price=Decimal("100"), stop_loss=Decimal("0.02"))
        ex.start()
        ex.notify_order_filled("o1", Decimal("100"), Decimal("1"))
        ex.notify_order_filled("o2", Decimal("97"), Decimal("1"))  # -3% < SL
        assert ex.state == ExecutorState.CLOSED

    def test_trailing_stop_path(self) -> None:
        ts = TrailingStop(
            activation_price_pct=Decimal("0.03"),
            trailing_delta_pct=Decimal("0.01"),
        )
        ex, market = _make(trailing_stop=ts)
        ex.start()
        ex.notify_order_filled("o1", Decimal("100"), Decimal("1"))
        ex.notify_price_updated(Decimal("104"))  # activates trailing stop
        ex.notify_price_updated(Decimal("102.5"))  # drops below trigger
        assert ex.state == ExecutorState.CLOSED

    def test_time_limit_path(self) -> None:
        ex, market = _make(time_limit_s=60)
        ex.start()
        ex.notify_order_filled("o1", Decimal("100"), Decimal("1"))
        assert ex.state == ExecutorState.ACTIVE
        t0 = datetime.datetime.now(datetime.UTC)
        ex._started_at = t0
        ex.tick(t0 + datetime.timedelta(seconds=61))
        assert ex.state == ExecutorState.CLOSED

    def test_state_at_each_step(self) -> None:
        ex, _ = _make()
        assert ex.state == ExecutorState.IDLE
        ex.start()
        assert ex.state == ExecutorState.ACTIVE
        ex.notify_order_filled("o1", Decimal("100"), Decimal("1"))
        assert ex.state == ExecutorState.ACTIVE
        ex.notify_order_filled("o2", Decimal("106"), Decimal("1"))
        assert ex.state == ExecutorState.CLOSED
