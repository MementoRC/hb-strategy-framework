"""Tests for StrategyOrchestrator."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from strategy_framework.orchestrator.simple_event_bus import SimpleEventBus
from strategy_framework.orchestrator.strategy_orchestrator import StrategyOrchestrator
from strategy_framework.primitives.actions import CreateExecutorAction, StopExecutorAction


def _make_orchestrator(event_bus=None):
    mock_access = MagicMock()
    mock_data = MagicMock()
    return StrategyOrchestrator(
        market_access=mock_access,
        market_data=mock_data,
        event_bus=event_bus,
    )


def _make_controller(controller_id: str = "ctrl-1", actions=None):
    ctrl = MagicMock()
    ctrl.controller_id = controller_id
    ctrl.evaluate.return_value = actions or []
    return ctrl


def test_register_and_unregister_controller():
    orch = _make_orchestrator()
    ctrl = _make_controller()
    orch.register_controller(ctrl)
    orch.unregister_controller("ctrl-1")  # no error


def test_evaluate_calls_controller():
    orch = _make_orchestrator()
    ctrl = _make_controller()
    orch.register_controller(ctrl)
    orch.evaluate()
    ctrl.evaluate.assert_called_once()


def test_evaluate_creates_executor_from_action():
    orch = _make_orchestrator()
    action = CreateExecutorAction(
        controller_id="ctrl-1",
        executor_config={"type": "stub"},
    )
    ctrl = _make_controller(actions=[action])
    orch.register_controller(ctrl)
    orch.evaluate()
    assert len(orch.get_active_executors("ctrl-1")) == 1


def test_submit_stop_action_removes_executor():
    orch = _make_orchestrator()
    action = CreateExecutorAction(
        controller_id="ctrl-1",
        executor_config={"type": "stub"},
    )
    ctrl = _make_controller(actions=[action])
    orch.register_controller(ctrl)
    orch.evaluate()
    executor_id = orch.get_active_executors("ctrl-1")[0]

    orch.submit_actions([StopExecutorAction(controller_id="ctrl-1", executor_id=executor_id)])
    assert orch.get_active_executors("ctrl-1") == []


def test_notification_routed_to_controller():
    orch = _make_orchestrator()
    action = CreateExecutorAction(
        controller_id="ctrl-1",
        executor_config={"type": "stub"},
    )
    ctrl = _make_controller(actions=[action])
    orch.register_controller(ctrl)
    orch.evaluate()
    executor_id = orch.get_active_executors("ctrl-1")[0]

    orch.submit_actions([StopExecutorAction(controller_id="ctrl-1", executor_id=executor_id)])
    ctrl.on_executor_notification.assert_called_once()


def test_event_bus_receives_event_on_stop():
    bus = SimpleEventBus()
    events = []
    bus.subscribe("executor.stopped", lambda p: events.append(p))

    orch = _make_orchestrator(event_bus=bus)
    action = CreateExecutorAction(
        controller_id="ctrl-1",
        executor_config={"type": "stub"},
    )
    ctrl = _make_controller(actions=[action])
    orch.register_controller(ctrl)
    orch.evaluate()
    executor_id = orch.get_active_executors("ctrl-1")[0]

    orch.submit_actions([StopExecutorAction(controller_id="ctrl-1", executor_id=executor_id)])
    assert len(events) == 1
    assert events[0]["executor_id"] == executor_id


def test_no_event_bus_no_error():
    """Orchestrator without event_bus should not raise on stop."""
    orch = _make_orchestrator(event_bus=None)
    action = CreateExecutorAction(
        controller_id="ctrl-1",
        executor_config={"type": "stub"},
    )
    ctrl = _make_controller(actions=[action])
    orch.register_controller(ctrl)
    orch.evaluate()
    executor_id = orch.get_active_executors("ctrl-1")[0]
    orch.submit_actions([StopExecutorAction(controller_id="ctrl-1", executor_id=executor_id)])
    # no error
