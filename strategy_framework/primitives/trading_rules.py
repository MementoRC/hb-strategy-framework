"""Trading rules primitive — exchange constraints for a trading pair."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class TradingRules(BaseModel):
    """Immutable snapshot of exchange trading rules for a pair.

    Mirrors the essential fields from hummingbot's TradingRule
    without the hummingbot dependency.
    """

    model_config = ConfigDict(frozen=True)

    trading_pair: str
    min_order_size: Decimal = Decimal("0")
    max_order_size: Decimal | None = None
    min_price_increment: Decimal = Decimal("0")
    min_base_amount_increment: Decimal = Decimal("0")
    min_notional_size: Decimal = Decimal("0")
    supports_limit_orders: bool = True
    supports_market_orders: bool = True
