from __future__ import annotations

from decimal import Decimal

import pytest
from strategy_framework.executors.base import ExecutorConfigBase
from strategy_framework.executors.triple_barrier import TripleBarrierExecutorConfig
from strategy_framework.primitives.enums import TradeType
from strategy_framework.primitives.triple_barrier import TripleBarrierConfig
from strategy_framework.primitives.trailing_stop import TrailingStop


def _tb_config(**kwargs: object) -> TripleBarrierExecutorConfig:
    defaults: dict[str, object] = dict(
        trading_pair="BTC-USDT",
        side=TradeType.BUY,
        entry_price=Decimal("50000"),
        amount=Decimal("0.01"),
        triple_barrier=TripleBarrierConfig(
            stop_loss=Decimal("0.02"),
            take_profit=Decimal("0.05"),
            time_limit_s=3600,
        ),
    )
    defaults.update(kwargs)
    return TripleBarrierExecutorConfig(**defaults)  # type: ignore[arg-type]


class TestTripleBarrierExecutorConfig:
    def test_is_executor_config_base(self) -> None:
        assert isinstance(_tb_config(), ExecutorConfigBase)

    def test_trailing_stop_defaults_to_none(self) -> None:
        assert _tb_config().trailing_stop is None

    def test_activation_bounds_defaults_to_none(self) -> None:
        assert _tb_config().activation_bounds is None

    def test_trailing_stop_can_be_set(self) -> None:
        ts = TrailingStop(activation_price_pct=Decimal("0.02"), trailing_delta_pct=Decimal("0.01"))
        config = _tb_config(trailing_stop=ts)
        assert config.trailing_stop == ts
