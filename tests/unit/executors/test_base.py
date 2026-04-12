from __future__ import annotations

from decimal import Decimal

import pytest
from strategy_framework.config.base import StrategyConfigBase
from strategy_framework.executors.base import (
    ExecutorBase,
    ExecutorConfigBase,
    ExecutorState,
    ExecutorStateError,
)
from strategy_framework.primitives.enums import CloseType
from strategy_framework.testing.mock_market import MockMarketAccess


class ConcreteConfig(ExecutorConfigBase):
    pass


class ConcreteExecutor(ExecutorBase):
    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.started_count: int = 0
        self.stopped_args: list[CloseType] = []

    def on_started(self) -> None:
        self.started_count += 1

    def on_stopped(self, close_type: CloseType) -> None:
        self.stopped_args.append(close_type)


def make_executor() -> ConcreteExecutor:
    market = MockMarketAccess()
    config = ConcreteConfig()
    return ConcreteExecutor(market=market, config=config)


class TestExecutorState:
    def test_all_four_states_exist(self) -> None:
        members = {s.name for s in ExecutorState}
        assert members == {"IDLE", "ACTIVE", "CLOSING", "CLOSED"}

    def test_state_count(self) -> None:
        assert len(ExecutorState) == 4

    def test_state_error_is_exception(self) -> None:
        with pytest.raises(ExecutorStateError, match="bad transition"):
            raise ExecutorStateError("bad transition")


class TestExecutorConfigBase:
    def test_is_strategy_config_base(self) -> None:
        config = ConcreteConfig()
        assert isinstance(config, StrategyConfigBase)


class TestExecutorBaseStateMachine:
    def test_initial_state_is_idle(self) -> None:
        ex = make_executor()
        assert ex.state == ExecutorState.IDLE

    def test_start_transitions_to_active(self) -> None:
        ex = make_executor()
        ex.start()
        assert ex.state == ExecutorState.ACTIVE

    def test_start_calls_on_started(self) -> None:
        ex = make_executor()
        ex.start()
        assert ex.started_count == 1

    def test_stop_from_active_transitions_to_closed(self) -> None:
        ex = make_executor()
        ex.start()
        ex.stop(CloseType.TAKE_PROFIT)
        assert ex.state == ExecutorState.CLOSED

    def test_stop_calls_on_stopped_with_close_type(self) -> None:
        ex = make_executor()
        ex.start()
        ex.stop(CloseType.STOP_LOSS)
        assert ex.stopped_args == [CloseType.STOP_LOSS]

    def test_double_stop_is_noop(self) -> None:
        ex = make_executor()
        ex.start()
        ex.stop(CloseType.TAKE_PROFIT)
        ex.stop(CloseType.TAKE_PROFIT)  # must not raise, still CLOSED
        assert ex.state == ExecutorState.CLOSED
        assert len(ex.stopped_args) == 1

    def test_invalid_transition_raises(self) -> None:
        ex = make_executor()
        with pytest.raises(ExecutorStateError):
            ex.stop(CloseType.TAKE_PROFIT)  # cannot stop from IDLE

    def test_state_is_read_only(self) -> None:
        ex = make_executor()
        with pytest.raises(AttributeError):
            ex.state = ExecutorState.CLOSED  # type: ignore[misc]


class TestExecutorBaseHooksFireBeforeBus:
    def test_hook_fires_before_bus_handler(self) -> None:
        order: list[str] = []
        market = MockMarketAccess()

        class TrackingExecutor(ExecutorBase):
            def on_order_filled(self, order_id: str, price: Decimal, amount: Decimal) -> None:
                order.append("hook")

        ex = TrackingExecutor(market=market, config=ConcreteConfig())
        ex.bus.subscribe("order.filled", lambda _: order.append("bus"))
        ex.start()
        ex.notify_order_filled("o1", Decimal("100"), Decimal("1"))
        assert order == ["hook", "bus"]
