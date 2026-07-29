"""PNLCalculatorMixin — trade PnL calculation using protocol-typed host inputs.

Ported from hummingbot/strategy_v2/executors/mixins/pnl_calculator.py.
Template methods replaced with PnLHostProtocol property reads.
All values exposed as @property (not methods as in hummingbot).
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from strategy_framework.protocols.composites import PnLHostProtocol, PnLProtocol


class PNLCalculatorMixin:
    """Mixin for single-entry/exit PnL calculation.

    Applies to executors with one open leg and one close leg
    (e.g., position, DCA entry). Does NOT apply to grid or arbitrage.

    Usage:
        class MyExecutor(PNLCalculatorMixin):
            @property
            def entry_price(self) -> Decimal: ...
            @property
            def close_price(self) -> Decimal: ...
            @property
            def open_filled_amount_quote(self) -> Decimal: ...
            @property
            def trade_side(self) -> TradeType: ...
            @property
            def cum_fees_raw(self) -> Decimal: ...

    No state, no _init_ required — all properties are pure computations.
    """

    @property
    def trade_pnl_pct(self: PnLHostProtocol) -> Decimal:
        """PnL percentage excluding fees.

        BUY:  (close - entry) / entry
        SELL: (entry - close) / entry
        Returns 0 if entry_price is 0 (no fill yet).
        """
        from strategy_framework.hb_compat.common import TradeType

        if self.entry_price == Decimal("0"):
            return Decimal("0")
        if self.trade_side == TradeType.BUY:
            return (self.close_price - self.entry_price) / self.entry_price
        return (self.entry_price - self.close_price) / self.entry_price

    @property
    def trade_pnl_quote(self: PnLHostProtocol) -> Decimal:
        """PnL in quote currency excluding fees."""
        return cast("PnLProtocol", self).trade_pnl_pct * self.open_filled_amount_quote

    @property
    def cum_fees_quote(self: PnLHostProtocol) -> Decimal:
        """Cumulative fees in quote currency."""
        return self.cum_fees_raw

    @property
    def net_pnl_quote(self: PnLHostProtocol) -> Decimal:
        """Net PnL in quote currency after fees."""
        pnl = cast("PnLProtocol", self)
        return pnl.trade_pnl_quote - pnl.cum_fees_quote

    @property
    def net_pnl_pct(self: PnLHostProtocol) -> Decimal:
        """Net PnL percentage after fees.

        Returns 0 if open_filled_amount_quote is 0 (no fill yet).
        """
        if self.open_filled_amount_quote <= Decimal("0"):
            return Decimal("0")
        return cast("PnLProtocol", self).net_pnl_quote / self.open_filled_amount_quote
