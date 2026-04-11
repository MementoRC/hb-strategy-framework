"""Tests for ExecutorProtocol and OrderProtocol."""

from decimal import Decimal
from typing import Any

from strategy_framework.primitives.enums import CloseType, RunnableStatus
from strategy_framework.protocols.executor import ExecutorProtocol
from strategy_framework.protocols.order import TrackedOrderProtocol


class TestExecutorProtocol:
    def test_is_runtime_checkable(self):
        assert not isinstance(object(), ExecutorProtocol)

    def test_concrete_satisfies(self):
        class FakeExecutor:
            close_type: CloseType | None = None
            status: RunnableStatus = RunnableStatus.NOT_STARTED

            def place_order(
                self, order_type: str, side: str, amount: Decimal, price: Decimal
            ) -> str:
                return "ord_1"

            def cancel_order(self, order_id: str) -> None:
                pass

            @property
            def net_pnl_pct(self) -> Decimal:
                return Decimal("0")

            @property
            def net_pnl_quote(self) -> Decimal:
                return Decimal("0")

            @property
            def is_done(self) -> bool:
                return False

            def early_stop(self, keep_position: bool = False) -> None:
                pass

            def update_live(self, update_data: dict[str, Any]) -> None:
                pass

        assert isinstance(FakeExecutor(), ExecutorProtocol)


class TestTrackedOrderProtocol:
    def test_is_runtime_checkable(self):
        assert not isinstance(object(), TrackedOrderProtocol)

    def test_concrete_satisfies(self):
        class FakeOrder:
            @property
            def order_id(self) -> str:
                return "ord_1"

            @property
            def is_filled(self) -> bool:
                return False

            @property
            def is_open(self) -> bool:
                return True

            @property
            def filled_amount(self) -> Decimal:
                return Decimal("0")

            @property
            def average_price(self) -> Decimal:
                return Decimal("50000")

        assert isinstance(FakeOrder(), TrackedOrderProtocol)
