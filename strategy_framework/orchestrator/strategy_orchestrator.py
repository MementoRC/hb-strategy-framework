"""StrategyOrchestrator — wires controllers, executors, and market protocols."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from strategy_framework.orchestrator.executor_manager import ExecutorManager
from strategy_framework.primitives.actions import (
    CreateExecutorAction,  # noqa: TC001 — isinstance() check
    StopExecutorAction,  # noqa: TC001 — isinstance() check
    _ExecutorAction,
)
from strategy_framework.primitives.enums import RunnableStatus  # noqa: TC001 — runtime value access

if TYPE_CHECKING:
    from strategy_framework.primitives.notification import ExecutorNotification
    from strategy_framework.protocols.event_bus import EventBusProtocol
    from strategy_framework.protocols.market import MarketAccessProtocol
    from strategy_framework.protocols.market_data import MarketDataProtocol


class StrategyOrchestrator:
    """Pull-model orchestrator. Host calls evaluate() each tick."""

    def __init__(
        self,
        market_access: MarketAccessProtocol,
        market_data: MarketDataProtocol,
        event_bus: EventBusProtocol | None = None,
    ) -> None:
        self._market_data = market_data
        self._event_bus = event_bus
        self._executor_manager = ExecutorManager(market_access=market_access)
        self._controllers: dict[str, Any] = {}

    def register_controller(self, controller: Any) -> None:
        self._controllers[controller.controller_id] = controller

    def unregister_controller(self, controller_id: str) -> None:
        self._controllers.pop(controller_id, None)

    def evaluate(self) -> None:
        """Call each controller, process returned actions."""
        for controller in list(self._controllers.values()):
            actions = controller.evaluate(self._market_data)
            if actions:
                self.submit_actions(actions)

    def submit_actions(self, actions: list[_ExecutorAction]) -> None:
        for action in actions:
            if isinstance(action, CreateExecutorAction):
                self._executor_manager.create_executor(
                    action,
                    on_notify=self._on_executor_notification,
                )
            elif isinstance(action, StopExecutorAction):
                self._executor_manager.stop_executor(action.executor_id)

    def get_executor_state(self, executor_id: str) -> RunnableStatus:
        return self._executor_manager.get_state(executor_id)

    def get_active_executors(self, controller_id: str) -> list[str]:
        return self._executor_manager.get_active(controller_id)

    def _on_executor_notification(self, notification: ExecutorNotification) -> None:
        controller = self._controllers.get(notification.controller_id)
        if controller is not None and hasattr(controller, "on_executor_notification"):
            controller.on_executor_notification(notification)
        if self._event_bus is not None:
            self._event_bus.publish(
                f"executor.{notification.event}",
                {"executor_id": notification.executor_id, **notification.data},
            )
