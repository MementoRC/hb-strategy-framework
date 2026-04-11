"""Core protocol definitions for the strategy framework.

Defines the port interfaces that adapters must implement.
These protocols establish the contract between the domain layer
and external systems, following Hexagonal Architecture principles.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class StrategyProtocol(Protocol):
    """Protocol defining the interface for trading strategies.

    All strategy implementations must conform to this protocol
    to be compatible with the strategy framework.
    """

    @property
    def name(self) -> str:
        """Unique name identifying this strategy."""
        ...

    @property
    def is_running(self) -> bool:
        """Whether the strategy is currently active."""
        ...

    async def start(self) -> None:
        """Start the strategy execution."""
        ...

    async def stop(self) -> None:
        """Stop the strategy execution."""
        ...


@runtime_checkable
class MarketDataProviderProtocol(Protocol):
    """Protocol for components that provide market data to strategies."""

    async def get_mid_price(self, trading_pair: str) -> float:
        """Get the current mid price for a trading pair."""
        ...


@runtime_checkable
class OrderExecutorProtocol(Protocol):
    """Protocol for components that execute orders on behalf of strategies."""

    async def place_order(
        self,
        trading_pair: str,
        side: str,
        amount: float,
        price: float | None = None,
    ) -> str:
        """Place an order and return the order ID."""
        ...

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order by ID. Returns True if successful."""
        ...
