"""MockMarketData — test implementation of MarketDataProtocol."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from decimal import Decimal

    from strategy_framework.primitives.candle import CandleData
    from strategy_framework.primitives.order_book import OrderBookSnapshot


class MockMarketData:
    """Mock market data for testing controllers.

    Configurable prices, order books, and candles via set_* methods.
    Satisfies MarketDataProtocol.
    """

    def __init__(self) -> None:
        self._mid_prices: dict[str, Decimal] = {}
        self._order_books: dict[str, OrderBookSnapshot] = {}
        self._candles: dict[tuple[str, str], list[CandleData]] = {}

    def get_mid_price(self, trading_pair: str) -> Decimal:
        return self._mid_prices[trading_pair]

    def get_order_book_snapshot(self, trading_pair: str) -> OrderBookSnapshot:
        return self._order_books[trading_pair]

    async def get_candles(self, trading_pair: str, interval: str, limit: int) -> list[CandleData]:
        return self._candles[(trading_pair, interval)][:limit]

    # Test setup helpers
    def set_mid_price(self, trading_pair: str, price: Decimal) -> None:
        self._mid_prices[trading_pair] = price

    def set_order_book_snapshot(self, trading_pair: str, snapshot: OrderBookSnapshot) -> None:
        self._order_books[trading_pair] = snapshot

    def set_candles(self, trading_pair: str, interval: str, candles: list[CandleData]) -> None:
        self._candles[(trading_pair, interval)] = candles
