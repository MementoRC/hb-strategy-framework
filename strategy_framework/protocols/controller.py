"""ControllerProtocol — contract for controller implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from strategy_framework.primitives.actions import _ExecutorAction


@runtime_checkable
class ControllerProtocol(Protocol):
    """Contract for strategy controllers."""

    @property
    def controller_id(self) -> str: ...

    @property
    def processed_data(self) -> dict[str, Any]: ...

    def determine_executor_actions(self) -> list[_ExecutorAction]: ...

    async def update_processed_data(self) -> None: ...
