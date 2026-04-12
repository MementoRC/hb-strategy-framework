"""Tests for MockMarketAccess."""

from decimal import Decimal

from strategy_framework.protocols.market import MarketAccessProtocol
from strategy_framework.testing.mock_market import MockMarketAccess


class TestMockMarketAccess:
    def test_satisfies_protocol(self):
        mock = MockMarketAccess()
        assert isinstance(mock, MarketAccessProtocol)

    def test_place_order_returns_id(self):
        mock = MockMarketAccess()
        order_id = mock.place_order("limit", "buy", Decimal("1.0"), Decimal("50000"))
        assert order_id.startswith("mock_")

    def test_place_order_records_history(self):
        mock = MockMarketAccess()
        mock.place_order("limit", "buy", Decimal("1.0"), Decimal("50000"))
        assert len(mock.order_history) == 1
        assert mock.order_history[0]["side"] == "buy"
        assert mock.order_history[0]["amount"] == Decimal("1.0")

    def test_cancel_order_records(self):
        mock = MockMarketAccess()
        order_id = mock.place_order("limit", "buy", Decimal("1.0"), Decimal("50000"))
        mock.cancel_order(order_id)
        assert order_id in mock.cancelled_orders

    def test_get_mid_price_configurable(self):
        mock = MockMarketAccess(mid_price=Decimal("42000"))
        assert mock.get_mid_price() == Decimal("42000")

    def test_set_mid_price(self):
        mock = MockMarketAccess()
        mock.set_mid_price(Decimal("55000"))
        assert mock.get_mid_price() == Decimal("55000")

    def test_unique_order_ids(self):
        mock = MockMarketAccess()
        id1 = mock.place_order("limit", "buy", Decimal("1"), Decimal("50000"))
        id2 = mock.place_order("limit", "sell", Decimal("1"), Decimal("50000"))
        assert id1 != id2

    def test_get_available_balance_returns_zero_by_default(self) -> None:
        market = MockMarketAccess()
        assert market.get_available_balance("USDT") == Decimal("0")

    def test_set_and_get_balance_round_trip(self) -> None:
        market = MockMarketAccess()
        market.set_balance("BTC", Decimal("2.5"))
        assert market.get_available_balance("BTC") == Decimal("2.5")

    def test_set_balance_does_not_affect_other_currencies(self) -> None:
        market = MockMarketAccess()
        market.set_balance("BTC", Decimal("1.0"))
        assert market.get_available_balance("ETH") == Decimal("0")
