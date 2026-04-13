"""Tests for ExecutorManager."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from strategy_framework.orchestrator.executor_manager import ExecutorManager
from strategy_framework.primitives.actions import CreateExecutorAction, StopExecutorAction
from strategy_framework.primitives.enums import RunnableStatus


def _create_action(controller_id: str = "ctrl-1") -> CreateExecutorAction:
    return CreateExecutorAction(
        controller_id=controller_id,
        executor_config={"type": "stub"},
    )


def test_create_executor_returns_id():
    manager = ExecutorManager(market_access=MagicMock())
    eid = manager.create_executor(_create_action(), on_notify=MagicMock())
    assert isinstance(eid, str)
    assert len(eid) > 0


def test_created_executor_is_active():
    manager = ExecutorManager(market_access=MagicMock())
    eid = manager.create_executor(_create_action(), on_notify=MagicMock())
    assert eid in manager.get_active("ctrl-1")


def test_stop_executor_removes_from_active():
    manager = ExecutorManager(market_access=MagicMock())
    eid = manager.create_executor(_create_action(), on_notify=MagicMock())
    manager.stop_executor(eid)
    assert eid not in manager.get_active("ctrl-1")


def test_get_state_active():
    manager = ExecutorManager(market_access=MagicMock())
    eid = manager.create_executor(_create_action(), on_notify=MagicMock())
    assert manager.get_state(eid) == RunnableStatus.RUNNING


def test_get_state_unknown_raises():
    manager = ExecutorManager(market_access=MagicMock())
    with pytest.raises(KeyError):
        manager.get_state("nonexistent-id")


def test_get_active_filters_by_controller():
    manager = ExecutorManager(market_access=MagicMock())
    eid1 = manager.create_executor(_create_action("ctrl-1"), on_notify=MagicMock())
    eid2 = manager.create_executor(_create_action("ctrl-2"), on_notify=MagicMock())
    assert eid1 in manager.get_active("ctrl-1")
    assert eid2 not in manager.get_active("ctrl-1")


def test_stop_executor_calls_on_notify():
    manager = ExecutorManager(market_access=MagicMock())
    on_notify = MagicMock()
    eid = manager.create_executor(_create_action(), on_notify=on_notify)
    manager.stop_executor(eid)
    on_notify.assert_called_once()
    notification = on_notify.call_args[0][0]
    assert notification.event == "stopped"
    assert notification.executor_id == eid
