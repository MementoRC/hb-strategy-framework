"""MarketAccessProtocol — dependency injection interface for market operations.

This is the key abstraction enabling both live trading and simulation:
- Live: inject connector-bound methods via functools.partial
- Simulation: inject hb-market-simulator methods
- Testing: inject mock callables
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from decimal import Decimal


class PlaceOrderSignature(Protocol):
    """Callable signature for placing an order."""

    def __call__(  # pragma: no cover
        self,
        order_type: str,
        side: str,
        amount: Decimal,
        price: Decimal,
    ) -> str:
        """Place an order, return the client order ID."""
        ...


class CancelOrderSignature(Protocol):
    """Callable signature for cancelling an order."""

    def __call__(self, order_id: str) -> None:  # pragma: no cover
        """Cancel an order by its client order ID."""
        ...


class GetMidPriceSignature(Protocol):
    """Callable signature for getting current mid price."""

    def __call__(self) -> Decimal:  # pragma: no cover
        """Return the current mid price."""
        ...


@runtime_checkable
class MarketAccessProtocol(Protocol):
    """Protocol for market operations — the DI interface.

    Implementations:
    - Live: wraps connector methods via functools.partial
    - Simulator: wraps hb-market-simulator
    - Test: MockMarketAccess from testing module
    """

    def place_order(  # pragma: no cover
        self,
        order_type: str,
        side: str,
        amount: Decimal,
        price: Decimal,
    ) -> str:
        """Place an order, return the client order ID."""
        ...

    def cancel_order(self, order_id: str) -> None:  # pragma: no cover
        """Cancel an order by its client order ID."""
        ...

    def get_mid_price(self) -> Decimal:  # pragma: no cover
        """Return the current mid price for the trading pair."""
        ...

    def get_available_balance(self, currency: str) -> Decimal:  # pragma: no cover
        """Return available (unlocked) balance for the given currency."""
        ...
