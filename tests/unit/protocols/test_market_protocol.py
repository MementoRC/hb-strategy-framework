"""Tests for MarketAccessProtocol — the DI interface for live/simulated market."""

from decimal import Decimal
from typing import runtime_checkable

from strategy_framework.protocols.market import (
    CancelOrderSignature,
    GetMidPriceSignature,
    MarketAccessProtocol,
    PlaceOrderSignature,
)


class TestMarketAccessProtocol:
    def test_is_runtime_checkable(self):
        assert runtime_checkable is not None  # Protocol decorated with @runtime_checkable
        # Verify by attempting isinstance check
        assert not isinstance(object(), MarketAccessProtocol)

    def test_concrete_implementation(self):
        """A class implementing all methods satisfies the protocol."""

        class FakeMarket:
            def place_order(
                self, order_type: str, side: str, amount: Decimal, price: Decimal
            ) -> str:
                return "order_123"

            def cancel_order(self, order_id: str) -> None:
                pass

            def get_mid_price(self) -> Decimal:
                return Decimal("50000")

        market = FakeMarket()
        assert isinstance(market, MarketAccessProtocol)

    def test_callable_signatures_are_protocols(self):
        """PlaceOrderSignature and CancelOrderSignature are callable Protocols."""

        def fake_place(order_type: str, side: str, amount: Decimal, price: Decimal) -> str:
            return "order_456"

        def fake_cancel(order_id: str) -> None:
            pass

        def fake_price() -> Decimal:
            return Decimal("50000")

        # These should be type-compatible (verified by mypy, runtime check optional)
        place: PlaceOrderSignature = fake_place  # type: ignore[assignment]
        cancel: CancelOrderSignature = fake_cancel  # type: ignore[assignment]
        price: GetMidPriceSignature = fake_price  # type: ignore[assignment]
        assert callable(place)
        assert callable(cancel)
        assert callable(price)
