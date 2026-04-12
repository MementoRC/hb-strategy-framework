from __future__ import annotations

import datetime
from decimal import Decimal

from strategy_framework.executors.base import ExecutorConfigBase, ExecutorState
from strategy_framework.executors.triple_barrier import (
    TripleBarrierExecutor,
    TripleBarrierExecutorConfig,
)
from strategy_framework.primitives.enums import TradeType
from strategy_framework.primitives.trailing_stop import TrailingStop
from strategy_framework.primitives.triple_barrier import TripleBarrierConfig
from strategy_framework.testing.mock_market import MockMarketAccess


def _tb_config(**kwargs: object) -> TripleBarrierExecutorConfig:
    defaults: dict[str, object] = dict(
        trading_pair="BTC-USDT",
        side=TradeType.BUY,
        entry_price=Decimal("50000"),
        amount=Decimal("0.01"),
        triple_barrier=TripleBarrierConfig(
            stop_loss=Decimal("0.02"),
            take_profit=Decimal("0.05"),
            time_limit_s=3600,
        ),
    )
    defaults.update(kwargs)
    return TripleBarrierExecutorConfig(**defaults)  # type: ignore[arg-type]


class TestTripleBarrierExecutorConfig:
    def test_is_executor_config_base(self) -> None:
        assert isinstance(_tb_config(), ExecutorConfigBase)

    def test_trailing_stop_defaults_to_none(self) -> None:
        assert _tb_config().trailing_stop is None

    def test_activation_bounds_defaults_to_none(self) -> None:
        assert _tb_config().activation_bounds is None

    def test_trailing_stop_can_be_set(self) -> None:
        ts = TrailingStop(activation_price_pct=Decimal("0.02"), trailing_delta_pct=Decimal("0.01"))
        config = _tb_config(trailing_stop=ts)
        assert config.trailing_stop == ts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_tb_executor(
    entry_price: Decimal = Decimal("100"),
    amount: Decimal = Decimal("1"),
    stop_loss: Decimal = Decimal("0.02"),
    take_profit: Decimal = Decimal("0.05"),
    time_limit_s: int = 3600,
    trailing_stop: TrailingStop | None = None,
    activation_bounds: tuple[Decimal, Decimal] | None = None,
    mid_price: Decimal | None = None,
) -> tuple[TripleBarrierExecutor, MockMarketAccess]:
    market = MockMarketAccess()
    market.set_mid_price(mid_price if mid_price is not None else entry_price)
    config = TripleBarrierExecutorConfig(
        trading_pair="BTC-USDT",
        side=TradeType.BUY,
        entry_price=entry_price,
        amount=amount,
        triple_barrier=TripleBarrierConfig(
            stop_loss=stop_loss,
            take_profit=take_profit,
            time_limit_s=time_limit_s,
        ),
        trailing_stop=trailing_stop,
        activation_bounds=activation_bounds,
    )
    return TripleBarrierExecutor(market=market, config=config), market


# ---------------------------------------------------------------------------
# Entry / activation tests
# ---------------------------------------------------------------------------


class TestTripleBarrierExecutorEntry:
    def test_start_places_entry_order(self) -> None:
        ex, market = make_tb_executor()
        ex.start()
        assert len(market.order_history) == 1

    def test_start_within_activation_bounds_places_order(self) -> None:
        ex, market = make_tb_executor(
            entry_price=Decimal("50000"),
            activation_bounds=(Decimal("0.99"), Decimal("1.01")),
            mid_price=Decimal("50000"),
        )
        ex.start()
        assert ex.state == ExecutorState.ACTIVE
        assert len(market.order_history) == 1

    def test_start_outside_activation_bounds_stays_idle(self) -> None:
        ex, market = make_tb_executor(
            entry_price=Decimal("50000"),
            activation_bounds=(Decimal("0.99"), Decimal("1.01")),
            mid_price=Decimal("60000"),
        )
        ex.start()
        assert ex.state == ExecutorState.IDLE
        assert len(market.order_history) == 0

    def test_price_update_while_idle_triggers_entry_when_in_bounds(self) -> None:
        ex, market = make_tb_executor(
            entry_price=Decimal("50000"),
            activation_bounds=(Decimal("0.99"), Decimal("1.01")),
            mid_price=Decimal("60000"),
        )
        ex.start()
        assert ex.state == ExecutorState.IDLE
        market.set_mid_price(Decimal("50000"))
        ex.notify_price_updated(Decimal("50000"))
        assert ex.state == ExecutorState.ACTIVE


# ---------------------------------------------------------------------------
# Exit / barrier tests
# ---------------------------------------------------------------------------


class TestTripleBarrierExecutorExits:
    def test_take_profit_exit(self) -> None:
        ex, market = make_tb_executor(entry_price=Decimal("100"), take_profit=Decimal("0.05"))
        ex.start()
        ex.notify_order_filled("o1", Decimal("100"), Decimal("1"))
        ex.notify_order_filled("o2", Decimal("106"), Decimal("1"))  # +6% > TP 5%
        assert ex.state == ExecutorState.CLOSED

    def test_stop_loss_exit(self) -> None:
        ex, market = make_tb_executor(entry_price=Decimal("100"), stop_loss=Decimal("0.02"))
        ex.start()
        ex.notify_order_filled("o1", Decimal("100"), Decimal("1"))
        ex.notify_order_filled("o2", Decimal("97"), Decimal("1"))  # -3% < SL -2%
        assert ex.state == ExecutorState.CLOSED

    def test_time_limit_exit(self) -> None:
        ex, market = make_tb_executor(time_limit_s=60)
        ex.start()
        ex.notify_order_filled("o1", Decimal("100"), Decimal("1"))
        now = datetime.datetime.now(datetime.timezone.utc)
        ex._started_at = now
        ex.tick(now + datetime.timedelta(seconds=30))
        assert ex.state == ExecutorState.ACTIVE
        ex.tick(now + datetime.timedelta(seconds=61))
        assert ex.state == ExecutorState.CLOSED

    def test_trailing_stop_exit(self) -> None:
        ts = TrailingStop(
            activation_price_pct=Decimal("0.02"),
            trailing_delta_pct=Decimal("0.01"),
        )
        ex, market = make_tb_executor(entry_price=Decimal("100"), trailing_stop=ts)
        ex.start()
        ex.notify_order_filled("o1", Decimal("100"), Decimal("1"))
        ex.notify_price_updated(Decimal("103"))  # +3% → activates, sets trigger at +2%
        ex.notify_price_updated(Decimal("101.5"))  # +1.5% < trigger +2% → fires
        assert ex.state == ExecutorState.CLOSED

    def test_entry_order_failure_closes_executor(self) -> None:
        ex, market = make_tb_executor()
        ex.start()
        ex.notify_order_failed("o1", "insufficient balance")
        assert ex.state == ExecutorState.CLOSED

    def test_partial_fill_does_not_trigger_exit_prematurely(self) -> None:
        ex, market = make_tb_executor(entry_price=Decimal("100"), take_profit=Decimal("0.05"))
        ex.start()
        ex.notify_order_filled("o1", Decimal("100"), Decimal("0.5"))
        assert ex.state == ExecutorState.ACTIVE
        ex.notify_order_filled("o2", Decimal("100"), Decimal("0.5"))
        assert ex.state == ExecutorState.ACTIVE
