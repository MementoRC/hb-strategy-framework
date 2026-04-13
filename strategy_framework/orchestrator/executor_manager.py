"""ExecutorManager — lifecycle management for strategy executors."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from strategy_framework.primitives.notification import ExecutorNotification

from strategy_framework.primitives.actions import CreateExecutorAction, StopExecutorAction
from strategy_framework.primitives.enums import RunnableStatus
from strategy_framework.protocols.market import MarketAccessProtocol


class ExecutorManager:
    """Tracks active, completed, and failed executors."""

    def __init__(self, market_access: MarketAccessProtocol) -> None:
        self._market_access = market_access
        # executor_id -> (executor, controller_id)
        self._active: dict[str, tuple[Any, str]] = {}
        self._terminated: dict[str, tuple[Any, str]] = {}

    def create_executor(
        self,
        action: CreateExecutorAction,
        on_notify: Callable[[ExecutorNotification], None],
    ) -> str:
        """Create an executor, register notification callback, return its ID."""
        executor_id = str(uuid.uuid4())
        from strategy_framework.orchestrator._stub_executor import StubExecutor

        executor = StubExecutor(
            executor_id=executor_id,
            controller_id=action.controller_id,
            config=action.executor_config,
            market_access=self._market_access,
            on_notify=on_notify,
        )
        self._active[executor_id] = (executor, action.controller_id)
        return executor_id

    def stop_executor(self, executor_id: str) -> None:
        if executor_id not in self._active:
            return
        executor, controller_id = self._active.pop(executor_id)
        executor.stop()
        self._terminated[executor_id] = (executor, controller_id)

    def get_state(self, executor_id: str) -> RunnableStatus:
        if executor_id in self._active:
            return RunnableStatus.RUNNING
        if executor_id in self._terminated:
            return RunnableStatus.TERMINATED
        raise KeyError(f"Unknown executor: {executor_id}")

    def get_active(self, controller_id: str) -> list[str]:
        return [
            eid for eid, (_, cid) in self._active.items()
            if cid == controller_id
        ]

    def cleanup_completed(self) -> list[ExecutorNotification]:
        return []
