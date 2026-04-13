"""ThresholdController — minimal controller for integration testing.

Emits CreateExecutorAction when mid_price < buy_threshold.
NOT a real strategy — just enough to prove the orchestrator loop.
"""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from strategy_framework.primitives.actions import CreateExecutorAction, _ExecutorAction

if TYPE_CHECKING:
    from strategy_framework.primitives.notification import ExecutorNotification


class ThresholdController:
    """Emits CreateExecutorAction when price falls below threshold."""

    def __init__(
        self,
        controller_id: str,
        trading_pair: str,
        buy_threshold: Decimal,
        max_executors: int = 1,
    ) -> None:
        self.controller_id = controller_id
        self._trading_pair = trading_pair
        self._buy_threshold = buy_threshold
        self._max_executors = max_executors
        self._active_executor_ids: list[str] = []
        self._pending_creations: int = 0
        self.notifications_received: list[ExecutorNotification] = []

    def evaluate(self, market_data) -> list[_ExecutorAction]:
        active_count = len(self._active_executor_ids) + self._pending_creations
        if active_count >= self._max_executors:
            return []
        mid_price = market_data.get_mid_price(self._trading_pair)
        if mid_price < self._buy_threshold:
            self._pending_creations += 1
            return [
                CreateExecutorAction(
                    controller_id=self.controller_id,
                    executor_config={
                        "type": "stub",
                        "trading_pair": self._trading_pair,
                    },
                )
            ]
        return []

    def on_executor_notification(self, notification: ExecutorNotification) -> None:
        self.notifications_received.append(notification)
        if notification.event in ("completed", "stopped", "failed", "terminated"):
            if notification.executor_id in self._active_executor_ids:
                self._active_executor_ids.remove(notification.executor_id)
            elif self._pending_creations > 0:
                # Executor was spawned from a pending creation slot — release it
                self._pending_creations -= 1