from __future__ import annotations

from decimal import Decimal
from typing import Optional

from strategy_framework.executors.base import ExecutorConfigBase
from strategy_framework.primitives.enums import TradeType
from strategy_framework.primitives.trailing_stop import TrailingStop
from strategy_framework.primitives.triple_barrier import TripleBarrierConfig


class TripleBarrierExecutorConfig(ExecutorConfigBase):
    trading_pair: str
    side: TradeType
    entry_price: Decimal
    amount: Decimal
    triple_barrier: TripleBarrierConfig
    trailing_stop: Optional[TrailingStop] = None
    activation_bounds: Optional[tuple[Decimal, Decimal]] = None
