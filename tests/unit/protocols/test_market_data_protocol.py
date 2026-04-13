"""Tests for MarketDataProtocol structural typing."""

from decimal import Decimal

import pytest

from strategy_framework.primitives.candle import CandleData
from strategy_framework.primitives.order_book import OrderBookEntry, OrderBookSnapshot
from strategy_framework.protocols.market_data import MarketDataProtocol


class ConcreteMarketData:
    """Minimal implementation satisfying MarketDataProtocol."""

    def get_mid_price(self, trading_pair: str) -> Decimal:
        return Decimal("100.0")

    def get_order_book_snapshot(self, trading_pair: str) -> OrderBookSnapshot:
        return OrderBookSnapshot(
            timestamp=1700000000000,
            bids=[OrderBookEntry(price=Decimal("99"), quantity=Decimal("10"))],
            asks=[OrderBookEntry(price=Decimal("101"), quantity=Decimal("5"))],
        )

    async def get_candles(self, trading_pair: str, interval: str, limit: int) -> list[CandleData]:
        return [
            CandleData(
                timestamp=1700000000000,
                open=Decimal("100"),
                high=Decimal("105"),
                low=Decimal("99"),
                close=Decimal("103"),
                volume=Decimal("1500"),
            )
        ]


class TestMarketDataProtocol:
    """MarketDataProtocol is runtime-checkable and structurally typed."""

    def test_concrete_satisfies_protocol(self):
        provider = ConcreteMarketData()
        assert isinstance(provider, MarketDataProtocol)

    def test_get_mid_price(self):
        provider = ConcreteMarketData()
        price = provider.get_mid_price("BTC-USDT")
        assert price == Decimal("100.0")

    def test_get_order_book_snapshot(self):
        provider = ConcreteMarketData()
        snap = provider.get_order_book_snapshot("BTC-USDT")
        assert isinstance(snap, OrderBookSnapshot)
        assert snap.best_bid == Decimal("99")

    @pytest.mark.asyncio
    async def test_get_candles(self):
        provider = ConcreteMarketData()
        candles = await provider.get_candles("BTC-USDT", "1m", 100)
        assert len(candles) == 1
        assert isinstance(candles[0], CandleData)
        assert candles[0].close == Decimal("103")

    def test_incomplete_impl_fails_check(self):
        class Incomplete:
            def get_mid_price(self, trading_pair: str) -> Decimal:
                return Decimal("100")

        assert not isinstance(Incomplete(), MarketDataProtocol)
