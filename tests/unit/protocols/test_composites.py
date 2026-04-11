"""Tests for composite protocol joins."""

from decimal import Decimal

from strategy_framework.protocols.composites import (
    BarrierControlProtocol,
    PnLProtocol,
)


class TestPnLProtocol:
    def test_is_runtime_checkable(self):
        assert not isinstance(object(), PnLProtocol)

    def test_concrete_satisfies(self):
        class FakePnL:
            @property
            def net_pnl_pct(self) -> Decimal:
                return Decimal("0.05")

            @property
            def net_pnl_quote(self) -> Decimal:
                return Decimal("100")

            @property
            def cum_fees_quote(self) -> Decimal:
                return Decimal("2.5")

            @property
            def trade_pnl_pct(self) -> Decimal:
                return Decimal("0.052")

        assert isinstance(FakePnL(), PnLProtocol)


class TestBarrierControlProtocol:
    def test_is_runtime_checkable(self):
        assert not isinstance(object(), BarrierControlProtocol)
