"""DataRequirement — frozen declaration of a strategy's market data needs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class DataRequirement(BaseModel):
    """Declares what market data a strategy needs.

    Passed to the integration layer (e.g. hb_compat) which maps it to
    a concrete data provider config (e.g. hummingbot CandlesConfig).

    Attributes:
        source: Data provider identifier (e.g. "binance_perpetual").
        trading_pair: Market symbol (e.g. "BTC-USDT").
        interval: Candle interval (e.g. "1m", "5m", "1h").
        max_records: History depth hint for the provider. Must be >= the
            largest indicator window the strategy uses.
    """

    model_config = ConfigDict(frozen=True)

    source: str
    trading_pair: str
    interval: str
    max_records: int = 100
