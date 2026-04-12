"""Test data factories for common framework objects."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from strategy_framework.primitives.actions import (
    CreateExecutorAction,
    StopExecutorAction,
    UpdateExecutorAction,
)
from strategy_framework.primitives.triple_barrier import TripleBarrierConfig

if TYPE_CHECKING:
    from strategy_framework.protocols.order import TrackedOrderProtocol


class ConfigFactory:
    """Factory for creating test configuration objects."""

    @staticmethod
    def triple_barrier(
        stop_loss: Decimal = Decimal("0.03"),
        take_profit: Decimal = Decimal("0.05"),
        time_limit_s: int = 3600,
    ) -> TripleBarrierConfig:
        return TripleBarrierConfig(
            stop_loss=stop_loss,
            take_profit=take_profit,
            time_limit_s=time_limit_s,
        )


class ActionFactory:
    """Factory for creating test executor actions."""

    @staticmethod
    def create(
        controller_id: str = "test_ctrl",
        executor_config: dict[str, Any] | None = None,
    ) -> CreateExecutorAction:
        return CreateExecutorAction(
            controller_id=controller_id,
            executor_config=executor_config or {"type": "position", "pair": "BTC-USDT"},
        )

    @staticmethod
    def stop(
        controller_id: str = "test_ctrl",
        executor_id: str = "test_exec",
        keep_position: bool = False,
    ) -> StopExecutorAction:
        return StopExecutorAction(
            controller_id=controller_id,
            executor_id=executor_id,
            keep_position=keep_position,
        )

    @staticmethod
    def update(
        controller_id: str = "test_ctrl",
        executor_id: str = "test_exec",
        update_data: dict[str, Any] | None = None,
    ) -> UpdateExecutorAction:
        return UpdateExecutorAction(
            controller_id=controller_id,
            executor_id=executor_id,
            update_data=update_data or {},
        )


class _MockTrackedOrder:
    """Concrete implementation of TrackedOrderProtocol for tests."""

    def __init__(
        self,
        order_id: str,
        is_filled: bool,
        is_open: bool,
        filled_amount: Decimal,
        average_price: Decimal,
    ) -> None:
        self.order_id = order_id
        self.is_filled = is_filled
        self.is_open = is_open
        self.filled_amount = filled_amount
        self.average_price = average_price


class TrackedOrderFactory:
    """Factory for creating mock TrackedOrderProtocol instances."""

    @staticmethod
    def open_order(
        order_id: str = "mock_0001",
        amount: Decimal = Decimal("1.0"),
        price: Decimal = Decimal("100.0"),
        side: str = "BUY",
    ) -> TrackedOrderProtocol:
        """Return a mock open (unfilled) order."""
        return _MockTrackedOrder(
            order_id=order_id,
            is_filled=False,
            is_open=True,
            filled_amount=Decimal("0"),
            average_price=price,
        )

    @staticmethod
    def filled_order(
        order_id: str = "mock_0001",
        amount: Decimal = Decimal("1.0"),
        price: Decimal = Decimal("100.0"),
    ) -> TrackedOrderProtocol:
        """Return a mock fully-filled order. filled_amount=amount, is_filled=True."""
        return _MockTrackedOrder(
            order_id=order_id,
            is_filled=True,
            is_open=False,
            filled_amount=amount,
            average_price=price,
        )
