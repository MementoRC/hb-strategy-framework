"""Tests for test data factories."""

from decimal import Decimal

from strategy_framework.primitives.actions import CreateExecutorAction, StopExecutorAction
from strategy_framework.primitives.triple_barrier import TripleBarrierConfig
from strategy_framework.testing.factories import ActionFactory, ConfigFactory


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
