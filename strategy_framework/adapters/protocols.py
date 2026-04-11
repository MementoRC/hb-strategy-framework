"""Adapter-level protocol definitions.

Defines the interface that all adapters must implement to integrate
with the strategy framework. These extend or complement the core
protocols with adapter-specific concerns.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class AdapterProtocol(Protocol):
    """Protocol defining the interface for strategy framework adapters.

    Adapters bridge external systems (exchanges, data providers) with
    the core strategy framework, translating between external formats
    and internal domain models.
    """

    @property
    def name(self) -> str:
        """Unique name identifying this adapter."""
        ...

    @property
    def is_connected(self) -> bool:
        """Whether the adapter is currently connected."""
        ...

    async def connect(self) -> None:
        """Establish connection to the external system."""
        ...

    async def disconnect(self) -> None:
        """Disconnect from the external system."""
        ...
