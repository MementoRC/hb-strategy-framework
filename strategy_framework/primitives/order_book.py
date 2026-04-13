"""Order book snapshot primitive."""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class OrderBookEntry(BaseModel):
    """Single price/quantity level in an order book."""

    model_config = ConfigDict(frozen=True)

    price: Decimal
    quantity: Decimal


class OrderBookSnapshot(BaseModel):
    """Immutable snapshot of an order book at a point in time.

    Bids and asks are ordered best-first (highest bid first, lowest ask first).
    """

    model_config = ConfigDict(frozen=True)

    timestamp: int
    """Unix timestamp in milliseconds."""
    bids: list[OrderBookEntry]
    asks: list[OrderBookEntry]

    @property
    def best_bid(self) -> Decimal:
        """Highest bid price. Raises ValueError if bids are empty."""
        if not self.bids:
            msg = "bids are empty"
            raise ValueError(msg)
        return self.bids[0].price

    @property
    def best_ask(self) -> Decimal:
        """Lowest ask price. Raises ValueError if asks are empty."""
        if not self.asks:
            msg = "asks are empty"
            raise ValueError(msg)
        return self.asks[0].price

    @property
    def spread(self) -> Decimal:
        """Spread between best ask and best bid."""
        return self.best_ask - self.best_bid
