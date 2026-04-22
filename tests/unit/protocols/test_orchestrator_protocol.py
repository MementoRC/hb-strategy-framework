"""Tests for OrchestratorProtocol structural compliance."""

from __future__ import annotations

from strategy_framework.primitives.enums import RunnableStatus
from strategy_framework.protocols.orchestrator import OrchestratorProtocol


class ConcreteOrchestrator:
    def submit_actions(self, actions):
        pass

    def get_executor_state(self, executor_id):
        return RunnableStatus.RUNNING

    def get_active_executors(self, controller_id):
        return []


def test_concrete_orchestrator_satisfies_protocol():
    o = ConcreteOrchestrator()
    assert isinstance(o, OrchestratorProtocol)
