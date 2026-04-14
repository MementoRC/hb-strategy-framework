"""Tests for MockMarketData."""

from __future__ import annotations

from decimal import Decimal

import pytest

from strategy_framework.primitives.candle import CandleData
from strategy_framework.primitives.order_book import OrderBookEntry, OrderBookSnapshot
from strategy_framework.protocols.market_data import MarketDataProtocol
from strategy_framework.testing.mock_market_data import MockMarketData


def test_satisfies_protocol():
    mock = MockMarketData()
    assert isinstance(mock, MarketDataProtocol)


def test_get_mid_price():
    mock = MockMarketData()
    mock.set_mid_price("BTC-USDT", Decimal("100.0"))
    assert mock.get_mid_price("BTC-USDT") == Decimal("100.0")


def test_get_mid_price_unset_raises():
    mock = MockMarketData()
    with pytest.raises(KeyError):
        mock.get_mid_price("BTC-USDT")


def test_get_order_book_snapshot():
    mock = MockMarketData()
    snapshot = OrderBookSnapshot(
        timestamp=0,
        bids=[OrderBookEntry(price=Decimal("99"), quantity=Decimal("1"))],
        asks=[OrderBookEntry(price=Decimal("101"), quantity=Decimal("1"))],
    )
    mock.set_order_book_snapshot("BTC-USDT", snapshot)
    result = mock.get_order_book_snapshot("BTC-USDT")
    assert result == snapshot


def test_get_order_book_snapshot_unset_raises():
    mock = MockMarketData()
    with pytest.raises(KeyError):
        mock.get_order_book_snapshot("BTC-USDT")


@pytest.mark.asyncio
async def test_get_candles():
    mock = MockMarketData()
    candles = [
        CandleData(
            timestamp=1000,
            open=Decimal("100"),
            high=Decimal("105"),
            low=Decimal("98"),
            close=Decimal("102"),
            volume=Decimal("10"),
        )
    ]
    mock.set_candles("BTC-USDT", "1m", candles)
    result = await mock.get_candles("BTC-USDT", "1m", 1)
    assert result == candles


@pytest.mark.asyncio
async def test_get_candles_unset_raises():
    mock = MockMarketData()
    with pytest.raises(KeyError):
        await mock.get_candles("BTC-USDT", "1m", 1)
