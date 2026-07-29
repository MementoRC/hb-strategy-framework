"""Tests for PNLCalculatorMixin."""

from __future__ import annotations

from decimal import Decimal

from strategy_framework.hb_compat.common import TradeType
from strategy_framework.mixins.executor.pnl import PNLCalculatorMixin


def _make_executor(
    entry: str,
    close: str,
    filled_quote: str,
    side: TradeType,
    fees: str = "0",
) -> PNLCalculatorMixin:
    class ConcretePNL(PNLCalculatorMixin):
        @property
        def entry_price(self) -> Decimal:
            return Decimal(entry)

        @property
        def close_price(self) -> Decimal:
            return Decimal(close)

        @property
        def open_filled_amount_quote(self) -> Decimal:
            return Decimal(filled_quote)

        @property
        def trade_side(self) -> TradeType:
            return side

        @property
        def cum_fees_raw(self) -> Decimal:
            return Decimal(fees)

    return ConcretePNL()


def test_trade_pnl_pct_buy_profit() -> None:
    obj = _make_executor("100", "110", "1000", TradeType.BUY)
    assert obj.trade_pnl_pct == Decimal("0.1")


def test_trade_pnl_pct_buy_loss() -> None:
    obj = _make_executor("100", "90", "1000", TradeType.BUY)
    assert obj.trade_pnl_pct == Decimal("-0.1")


def test_trade_pnl_pct_sell_profit() -> None:
    obj = _make_executor("100", "90", "1000", TradeType.SELL)
    assert obj.trade_pnl_pct == Decimal("0.1")


def test_trade_pnl_pct_sell_loss() -> None:
    obj = _make_executor("100", "110", "1000", TradeType.SELL)
    assert obj.trade_pnl_pct == Decimal("-0.1")


def test_trade_pnl_pct_zero_entry_returns_zero() -> None:
    obj = _make_executor("0", "100", "1000", TradeType.BUY)
    assert obj.trade_pnl_pct == Decimal("0")


def test_trade_pnl_quote() -> None:
    obj = _make_executor("100", "110", "1000", TradeType.BUY)
    # trade_pnl_pct=0.1, filled_quote=1000 → trade_pnl_quote=100
    assert obj.trade_pnl_quote == Decimal("100")


def test_cum_fees_quote_reflects_raw_fees() -> None:
    obj = _make_executor("100", "110", "1000", TradeType.BUY, fees="5")
    assert obj.cum_fees_quote == Decimal("5")


def test_net_pnl_quote_deducts_fees() -> None:
    obj = _make_executor("100", "110", "1000", TradeType.BUY, fees="5")
    assert obj.net_pnl_quote == Decimal("95")


def test_net_pnl_pct_deducts_fees() -> None:
    # trade_pnl_pct=0.1, fees=5 on 1000 filled → fee_pct=0.005
    obj = _make_executor("100", "110", "1000", TradeType.BUY, fees="5")
    assert obj.net_pnl_pct == Decimal("0.095")


def test_net_pnl_pct_zero_filled_returns_zero() -> None:
    obj = _make_executor("100", "110", "0", TradeType.BUY)
    assert obj.net_pnl_pct == Decimal("0")
