"""OrchestratorProtocol — interface controllers use to submit actions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from strategy_framework.primitives.actions import _ExecutorAction
    from strategy_framework.primitives.enums import RunnableStatus


@runtime_checkable
class OrchestratorProtocol(Protocol):
    """What controllers and external consumers see of the orchestrator."""

    def submit_actions(self, actions: list[_ExecutorAction]) -> None:  # pragma: no cover
        """Accept a list of executor actions from a controller."""
        ...

    def get_executor_state(self, executor_id: str) -> RunnableStatus:  # pragma: no cover
        """Return the current status of the given executor."""
        ...

    def get_active_executors(self, controller_id: str) -> list[str]:  # pragma: no cover
        """Return executor IDs currently active for the given controller."""
        ...
