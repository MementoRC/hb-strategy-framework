"""Trading rules protocol — order sizing and price quantization."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from decimal import Decimal

    from strategy_framework.primitives.trading_rules import TradingRules


@runtime_checkable
class TradingRulesProtocol(Protocol):
    """Protocol for accessing exchange trading rules and quantization.

    Implementations:
    - LiveMarketAccess (hb-market-connector) — wraps ConnectorBase trading rules
    - Any mock/stub for testing
    """

    def get_trading_rules(self, trading_pair: str) -> TradingRules:
        """Get trading rules for a pair (min sizes, increments, etc.)."""
        ...

    def quantize_order_amount(self, trading_pair: str, amount: Decimal) -> Decimal:
        """Quantize an order amount to the exchange's minimum increment."""
        ...

    def quantize_order_price(self, trading_pair: str, price: Decimal) -> Decimal:
        """Quantize an order price to the exchange's minimum increment."""
        ...
