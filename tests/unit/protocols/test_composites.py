"""Tests for composite protocol joins."""

from decimal import Decimal

from strategy_framework.protocols.composites import (
    ActivationBoundsProtocol,
    BarrierControlProtocol,
    OrderTrackingProtocol,
    PnLProtocol,
    RetryProtocol,
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

            @property
            def trade_pnl_quote(self) -> Decimal:
                return Decimal("102.5")

        assert isinstance(FakePnL(), PnLProtocol)


class TestBarrierControlProtocol:
    def test_is_runtime_checkable(self):
        assert not isinstance(object(), BarrierControlProtocol)


class TestRetryProtocol:
    def test_concrete_satisfies(self):
        class FakeRetry:
            current_retries: int = 0
            max_retries: int = 3

            def increment_retries(self) -> None:
                self.current_retries += 1

        assert isinstance(FakeRetry(), RetryProtocol)


class TestOrderTrackingProtocol:
    def test_concrete_satisfies(self):
        class FakeOrderTracking:
            @property
            def open_orders(self) -> list[object]:
                return [{"order_id": "123"}]

            @property
            def close_orders(self) -> list[object]:
                return [{"order_id": "456"}]

            def update_tracked_order(self, order_id: str, **kwargs: object) -> None:
                pass

        assert isinstance(FakeOrderTracking(), OrderTrackingProtocol)


class TestActivationBoundsProtocol:
    def test_concrete_satisfies(self):
        class FakeActivationBounds:
            entry_price: Decimal = Decimal("100.0")
            activation_bounds: tuple[Decimal, Decimal] | None = (Decimal("0.99"), Decimal("1.01"))

        assert isinstance(FakeActivationBounds(), ActivationBoundsProtocol)
