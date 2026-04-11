"""Test data factories for common framework objects."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from strategy_framework.primitives.actions import (
    CreateExecutorAction,
    StopExecutorAction,
    UpdateExecutorAction,
)
from strategy_framework.primitives.triple_barrier import TripleBarrierConfig


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
