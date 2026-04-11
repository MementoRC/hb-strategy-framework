"""Hummingbot compatibility protocols.

Defines the runtime-checkable protocol that matches the interface
Hummingbot expects from strategy components, enabling seamless
integration as a drop-in replacement.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class StrategyBaseProtocol(Protocol):
    """Protocol matching Hummingbot's expected strategy interface.

    Implementations of this protocol can be used directly by
    Hummingbot's strategy orchestration layer.
    """

    @property
    def name(self) -> str:
        """Strategy name as registered in Hummingbot."""
        ...

    @property
    def is_running(self) -> bool:
        """Whether the strategy is currently active."""
        ...

    async def start(self) -> None:
        """Start strategy execution."""
        ...

    async def stop(self) -> None:
        """Stop strategy execution."""
        ...
