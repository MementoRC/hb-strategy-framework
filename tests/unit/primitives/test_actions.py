"""Tests for ExecutorAction types."""

from strategy_framework.primitives.actions import (
    CreateExecutorAction,
    StopExecutorAction,
    StoreExecutorAction,
    UpdateExecutorAction,
)


class TestCreateExecutorAction:
    def test_creation(self):
        action = CreateExecutorAction(
            controller_id="ctrl_1",
            executor_config={"type": "position", "pair": "BTC-USDT"},
        )
        assert action.controller_id == "ctrl_1"
        assert action.executor_config["type"] == "position"
        assert action.action_type == "create"


class TestStopExecutorAction:
    def test_creation(self):
        action = StopExecutorAction(
            controller_id="ctrl_1",
            executor_id="exec_123",
        )
        assert action.controller_id == "ctrl_1"
        assert action.executor_id == "exec_123"
        assert action.action_type == "stop"

    def test_keep_position_default(self):
        action = StopExecutorAction(controller_id="c", executor_id="e")
        assert action.keep_position is False

    def test_keep_position_explicit(self):
        action = StopExecutorAction(controller_id="c", executor_id="e", keep_position=True)
        assert action.keep_position is True


class TestUpdateExecutorAction:
    def test_creation(self):
        action = UpdateExecutorAction(
            controller_id="ctrl_1",
            executor_id="exec_123",
            update_data={"volatility": 0.05},
        )
        assert action.controller_id == "ctrl_1"
        assert action.executor_id == "exec_123"
        assert action.update_data == {"volatility": 0.05}
        assert action.action_type == "update"


class TestStoreExecutorAction:
    def test_creation(self):
        action = StoreExecutorAction(
            controller_id="ctrl_1",
            executor_id="exec_123",
        )
        assert action.action_type == "store"
