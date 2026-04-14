"""Tests for OrchestratorAdapter — host-framework composition layer."""
from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from strategy_framework.hb_compat import OrchestratorAdapter
from strategy_framework.orchestrator import StrategyOrchestrator


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def market_access():
    return MagicMock(name="market_access")


@pytest.fixture()
def market_data():
    return MagicMock(name="market_data")


@pytest.fixture()
def adapter(market_access, market_data):
    return OrchestratorAdapter(market_access, market_data)


# ── Construction ──────────────────────────────────────────────────────────────


class TestOrchestratorAdapterConstruction:
    def test_holds_strategy_orchestrator(self, adapter):
        assert isinstance(adapter.orchestrator, StrategyOrchestrator)

    def test_accepts_optional_event_bus(self, market_access, market_data):
        bus = MagicMock(name="event_bus")
        a = OrchestratorAdapter(market_access, market_data, event_bus=bus)
        assert a.orchestrator is not None

    def test_no_hummingbot_import(self):
        import strategy_framework.hb_compat.orchestrator_adapter as mod
        import sys

        hb_modules = [k for k in sys.modules if k.startswith("hummingbot")]
        assert not hb_modules, f"hummingbot was imported: {hb_modules}"


# ── evaluate() ────────────────────────────────────────────────────────────────


class TestEvaluate:
    def test_evaluate_drives_orchestrator(self, adapter, market_data):
        controller = MagicMock()
        controller.controller_id = "c1"
        controller.evaluate.return_value = []
        adapter.register_controller(controller)

        adapter.evaluate()

        controller.evaluate.assert_called_once_with(market_data)

    def test_evaluate_called_multiple_times(self, adapter, market_data):
        controller = MagicMock()
        controller.controller_id = "c1"
        controller.evaluate.return_value = []
        adapter.register_controller(controller)

        adapter.evaluate()
        adapter.evaluate()

        assert controller.evaluate.call_count == 2


# ── Controller management ─────────────────────────────────────────────────────


class TestControllerManagement:
    def test_register_controller(self, adapter, market_data):
        controller = MagicMock()
        controller.controller_id = "ctrl1"
        controller.evaluate.return_value = []
        adapter.register_controller(controller)

        adapter.evaluate()
        controller.evaluate.assert_called_once()

    def test_unregister_controller(self, adapter, market_data):
        controller = MagicMock()
        controller.controller_id = "ctrl1"
        controller.evaluate.return_value = []
        adapter.register_controller(controller)
        adapter.unregister_controller("ctrl1")

        adapter.evaluate()
        controller.evaluate.assert_not_called()


# ── OrchestratorProtocol delegation ──────────────────────────────────────────


class TestDelegation:
    def test_get_active_executors_returns_empty_by_default(self, adapter):
        result = adapter.get_active_executors("no-such-controller")
        assert result == []

    def test_get_executor_state_unknown_raises(self, adapter):
        from strategy_framework.orchestrator.executor_manager import ExecutorManager

        with pytest.raises(KeyError):
            adapter.get_executor_state("no-such-executor")

    def test_orchestrator_property_is_same_instance(self, adapter):
        orch1 = adapter.orchestrator
        orch2 = adapter.orchestrator
        assert orch1 is orch2
