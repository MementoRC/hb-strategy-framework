"""Tests for test data factories."""

from decimal import Decimal

from strategy_framework.primitives.actions import CreateExecutorAction, StopExecutorAction
from strategy_framework.primitives.triple_barrier import TripleBarrierConfig
from strategy_framework.protocols.order import TrackedOrderProtocol
from strategy_framework.testing.factories import ActionFactory, ConfigFactory, TrackedOrderFactory


class TestConfigFactory:
    def test_triple_barrier_default(self):
        config = ConfigFactory.triple_barrier()
        assert isinstance(config, TripleBarrierConfig)
        assert config.stop_loss > 0
        assert config.take_profit > 0

    def test_triple_barrier_custom(self):
        config = ConfigFactory.triple_barrier(stop_loss=Decimal("0.05"))
        assert config.stop_loss == Decimal("0.05")


class TestActionFactory:
    def test_create_action(self):
        action = ActionFactory.create(controller_id="ctrl_1")
        assert isinstance(action, CreateExecutorAction)
        assert action.controller_id == "ctrl_1"

    def test_stop_action(self):
        action = ActionFactory.stop(controller_id="ctrl_1", executor_id="exec_1")
        assert isinstance(action, StopExecutorAction)


class TestTrackedOrderFactory:
    def test_open_order_satisfies_protocol(self) -> None:
        order = TrackedOrderFactory.open_order()
        assert isinstance(order, TrackedOrderProtocol)
        assert order.order_id == "mock_0001"
        assert order.is_open is True
        assert order.is_filled is False
        assert order.filled_amount == Decimal("0")
        assert order.average_price == Decimal("100.0")

    def test_filled_order_satisfies_protocol(self) -> None:
        order = TrackedOrderFactory.filled_order(amount=Decimal("2.5"), price=Decimal("50000"))
        assert isinstance(order, TrackedOrderProtocol)
        assert order.is_filled is True
        assert order.is_open is False
        assert order.filled_amount == Decimal("2.5")
        assert order.average_price == Decimal("50000")

    def test_open_order_custom_id(self) -> None:
        order = TrackedOrderFactory.open_order(order_id="custom_001")
        assert order.order_id == "custom_001"
