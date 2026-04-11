"""Test harnesses for executors and controllers."""

from __future__ import annotations

from decimal import Decimal

from strategy_framework.testing.mock_market import MockMarketAccess


class ExecutorTestHarness:
    """Harness for testing executor implementations.

    Provides a MockMarketAccess and convenience methods for simulating
    market conditions during tests.
    """

    def __init__(self, mid_price: Decimal = Decimal("50000")) -> None:
        self.market = MockMarketAccess(mid_price=mid_price)

    def set_price(self, price: Decimal) -> None:
        """Simulate a price change."""
        self.market.set_mid_price(price)
