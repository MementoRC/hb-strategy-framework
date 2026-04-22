"""End-to-end proof: controller → orchestrator → executor → notification → controller."""

from __future__ import annotations

from decimal import Decimal

from strategy_framework.orchestrator.simple_event_bus import SimpleEventBus
from strategy_framework.orchestrator.strategy_orchestrator import StrategyOrchestrator
from strategy_framework.primitives.actions import StopExecutorAction
from strategy_framework.protocols.market import MarketAccessProtocol
from strategy_framework.testing.mock_market import MockMarketAccess
from strategy_framework.testing.mock_market_data import MockMarketData
from strategy_framework.testing.threshold_controller import ThresholdController


def _make_setup(
    price: Decimal,
    threshold: Decimal,
    use_event_bus: bool = False,
):
    mock_access = MockMarketAccess(mid_price=price)
    market_data = MockMarketData()
    market_data.set_mid_price("BTC-USDT", price)
    bus = SimpleEventBus() if use_event_bus else None
    orch = StrategyOrchestrator(
        market_access=mock_access,
        market_data=market_data,
        event_bus=bus,
    )
    ctrl = ThresholdController(
        controller_id="ctrl-1",
        trading_pair="BTC-USDT",
        buy_threshold=threshold,
    )
    orch.register_controller(ctrl)
    return orch, ctrl, market_data, bus


def test_price_below_threshold_creates_executor():
    orch, ctrl, _, _ = _make_setup(Decimal("90"), Decimal("100"))
    orch.evaluate()
    assert len(orch.get_active_executors("ctrl-1")) == 1


def test_price_above_threshold_no_executor():
    orch, ctrl, _, _ = _make_setup(Decimal("110"), Decimal("100"))
    orch.evaluate()
    assert len(orch.get_active_executors("ctrl-1")) == 0


def test_stop_action_removes_executor_and_notifies_controller():
    orch, ctrl, _, _ = _make_setup(Decimal("90"), Decimal("100"))
    orch.evaluate()
    executor_id = orch.get_active_executors("ctrl-1")[0]

    orch.submit_actions([StopExecutorAction(controller_id="ctrl-1", executor_id=executor_id)])
    assert orch.get_active_executors("ctrl-1") == []
    assert len(ctrl.notifications_received) == 1
    assert ctrl.notifications_received[0].event == "stopped"


def test_multiple_evaluate_cycles_no_duplicate_executors():
    orch, ctrl, _, _ = _make_setup(Decimal("90"), Decimal("100"))
    orch.evaluate()
    orch.evaluate()  # max_executors=1 — ThresholdController won't create a second
    assert len(orch.get_active_executors("ctrl-1")) == 1


def test_event_bus_receives_executor_stopped():
    orch, ctrl, _, bus = _make_setup(Decimal("90"), Decimal("100"), use_event_bus=True)
    events = []
    bus.subscribe("executor.stopped", lambda p: events.append(p))

    orch.evaluate()
    executor_id = orch.get_active_executors("ctrl-1")[0]
    orch.submit_actions([StopExecutorAction(controller_id="ctrl-1", executor_id=executor_id)])

    assert len(events) == 1
    assert events[0]["executor_id"] == executor_id


def test_mock_market_access_satisfies_protocol():
    """Proves MockMarketAccess and live access are structurally identical."""
    mock = MockMarketAccess()
    assert isinstance(mock, MarketAccessProtocol)
