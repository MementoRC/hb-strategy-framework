"""StubExecutor — minimal executor for testing ExecutorManager."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from strategy_framework.primitives.notification import ExecutorNotification
    from strategy_framework.protocols.market import MarketAccessProtocol


class StubExecutor:
    """Minimal executor that tracks state and calls on_notify on stop."""

    def __init__(
        self,
        executor_id: str,
        controller_id: str,
        config: dict[str, Any],
        market_access: MarketAccessProtocol,
        on_notify: Callable[[ExecutorNotification], None],
    ) -> None:
        self.executor_id = executor_id
        self.controller_id = controller_id
        self._on_notify = on_notify
        self._stopped = False

    def stop(self) -> None:
        from strategy_framework.primitives.notification import ExecutorNotification

        self._stopped = True
        self._on_notify(
            ExecutorNotification(
                executor_id=self.executor_id,
                controller_id=self.controller_id,
                event="stopped",
            )
        )
