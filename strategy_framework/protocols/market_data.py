"""Market data protocol — candles, orderbook, prices."""
from __future__ import annotations

from decimal import Decimal
from typing import Protocol, runtime_checkable

from strategy_framework.primitives.candle import CandleData
from strategy_framework.primitives.order_book import OrderBookSnapshot


@runtime_checkable
class MarketDataProtocol(Protocol):
    """Protocol for accessing market data (candles, orderbook, prices).

    Implementations:
    - LiveMarketData (hb-market-data) — wraps hummingbot MarketDataProvider
    - Any mock/stub for testing
    """

    def get_mid_price(self, trading_pair: str) -> Decimal:
        """Get the current mid price for a trading pair."""
        ...

    def get_order_book_snapshot(self, trading_pair: str) -> OrderBookSnapshot:
        """Get a point-in-time snapshot of the order book."""
        ...

    async def get_candles(
        self, trading_pair: str, interval: str, limit: int
    ) -> list[CandleData]:
        """Get recent OHLCV candles for a trading pair."""
        ...
