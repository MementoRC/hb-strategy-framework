"""Protocol-typed executor mixins.

Each mixin types self: against a host protocol from strategy_framework.protocols.composites.
Import the mixin you need; compose with MRO-safe _init_<mixin>() pattern.

Example:
    class MyExecutor(RetryMixin, TrailingStopMixin):
        max_retries: int = 3
        ...

        def __init__(self) -> None:
            self._init_retry()
            self._init_trailing_stop()
"""

from strategy_framework.mixins.executor.activation import ActivationBoundsMixin
from strategy_framework.mixins.executor.balance import BalanceValidationMixin
from strategy_framework.mixins.executor.order_tracking import OrderTrackingMixin
from strategy_framework.mixins.executor.pnl import PNLCalculatorMixin
from strategy_framework.mixins.executor.retry import RetryMixin
from strategy_framework.mixins.executor.shutdown import ShutdownMixin
from strategy_framework.mixins.executor.trailing_stop import TrailingStopMixin

__all__ = [
    "ActivationBoundsMixin",
    "BalanceValidationMixin",
    "OrderTrackingMixin",
    "PNLCalculatorMixin",
    "RetryMixin",
    "ShutdownMixin",
    "TrailingStopMixin",
]
