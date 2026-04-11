"""Integration tests verifying concrete classes satisfy protocols."""

from decimal import Decimal

from strategy_framework.protocols.market import MarketAccessProtocol
from strategy_framework.testing.mock_market import MockMarketAccess


class TestProtocolSatisfaction:
    def test_mock_market_satisfies_market_protocol(self):
        """MockMarketAccess must satisfy MarketAccessProtocol."""
        mock = MockMarketAccess()
        assert isinstance(mock, MarketAccessProtocol)

        # Verify actual functionality, not just isinstance
        order_id = mock.place_order("limit", "buy", Decimal("1.0"), Decimal("50000"))
        assert isinstance(order_id, str)
        mock.cancel_order(order_id)
        price = mock.get_mid_price()
        assert isinstance(price, Decimal)
