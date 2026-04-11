"""MockMarketAccess — test implementation of MarketAccessProtocol."""

from __future__ import annotations

from decimal import Decimal
from typing import Any


class MockMarketAccess:
    """Mock market for testing executors and controllers.

    Records all orders placed and cancelled. Configurable mid price.
    Satisfies MarketAccessProtocol.
    """

    def __init__(self, mid_price: Decimal = Decimal("50000")) -> None:
        self._mid_price = mid_price
        self._order_counter = 0
        self.order_history: list[dict[str, Any]] = []
        self.cancelled_orders: set[str] = set()

    def place_order(
        self,
        order_type: str,
        side: str,
        amount: Decimal,
        price: Decimal,
    ) -> str:
        self._order_counter += 1
        order_id = f"mock_{self._order_counter:04d}"
        self.order_history.append({
            "order_id": order_id,
            "order_type": order_type,
            "side": side,
            "amount": amount,
            "price": price,
        })
        return order_id

    def cancel_order(self, order_id: str) -> None:
        self.cancelled_orders.add(order_id)

    def get_mid_price(self) -> Decimal:
        return self._mid_price

    def set_mid_price(self, price: Decimal) -> None:
        """Update the mock mid price (for simulating price movement in tests)."""
        self._mid_price = price
