"""Integration test: verify a mock MarketData implementation satisfies the protocol."""
from decimal import Decimal

import pytest

from strategy_framework import (
    CandleData,
    MarketDataProtocol,
    OrderBookEntry,
    OrderBookSnapshot,
    TradingRules,
    TradingRulesProtocol,
)


class MockMarketData:
    """Test double that satisfies both MarketDataProtocol and TradingRulesProtocol."""

    def __init__(self, mid_price: Decimal = Decimal("100")):
        self._mid_price = mid_price

    def get_mid_price(self, trading_pair: str) -> Decimal:
        return self._mid_price

    def get_order_book_snapshot(self, trading_pair: str) -> OrderBookSnapshot:
        spread = Decimal("1")
        return OrderBookSnapshot(
            timestamp=0,
            bids=[OrderBookEntry(price=self._mid_price - spread / 2, quantity=Decimal("10"))],
            asks=[OrderBookEntry(price=self._mid_price + spread / 2, quantity=Decimal("10"))],
        )

    async def get_candles(
        self, trading_pair: str, interval: str, limit: int
    ) -> list[CandleData]:
        return [
            CandleData(
                timestamp=i * 60_000,
                open=self._mid_price,
                high=self._mid_price + 1,
                low=self._mid_price - 1,
                close=self._mid_price,
                volume=Decimal("100"),
            )
            for i in range(limit)
        ]

    def get_trading_rules(self, trading_pair: str) -> TradingRules:
        return TradingRules(
            trading_pair=trading_pair,
            min_order_size=Decimal("0.001"),
            min_price_increment=Decimal("0.01"),
            min_base_amount_increment=Decimal("0.001"),
            min_notional_size=Decimal("10"),
        )

    def quantize_order_amount(self, trading_pair: str, amount: Decimal) -> Decimal:
        rules = self.get_trading_rules(trading_pair)
        return (amount // rules.min_base_amount_increment) * rules.min_base_amount_increment

    def quantize_order_price(self, trading_pair: str, price: Decimal) -> Decimal:
        rules = self.get_trading_rules(trading_pair)
        return (price // rules.min_price_increment) * rules.min_price_increment


class TestProtocolSatisfaction:
    """Verify MockMarketData satisfies both protocols."""

    def test_satisfies_market_data_protocol(self):
        assert isinstance(MockMarketData(), MarketDataProtocol)

    def test_satisfies_trading_rules_protocol(self):
        assert isinstance(MockMarketData(), TradingRulesProtocol)

    def test_mid_price_flows(self):
        data = MockMarketData(mid_price=Decimal("50000"))
        assert data.get_mid_price("BTC-USDT") == Decimal("50000")

    def test_order_book_reflects_mid_price(self):
        data = MockMarketData(mid_price=Decimal("100"))
        snap = data.get_order_book_snapshot("BTC-USDT")
        assert snap.best_bid == Decimal("99.5")
        assert snap.best_ask == Decimal("100.5")

    @pytest.mark.asyncio
    async def test_candles_respect_limit(self):
        data = MockMarketData()
        candles = await data.get_candles("BTC-USDT", "1m", 5)
        assert len(candles) == 5

    def test_quantize_amount(self):
        data = MockMarketData()
        assert data.quantize_order_amount("BTC-USDT", Decimal("1.23456")) == Decimal("1.234")

    def test_quantize_price(self):
        data = MockMarketData()
        assert data.quantize_order_price("BTC-USDT", Decimal("100.567")) == Decimal("100.56")
