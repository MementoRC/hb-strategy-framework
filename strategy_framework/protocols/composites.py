"""Pre-built composite protocol joins for common mixin requirements.

These combine simple protocols into the exact interface a specific mixin needs.
Mixin methods type `self:` against these composites.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from decimal import Decimal

    from strategy_framework.primitives.enums import CloseType, RunnableStatus
    from strategy_framework.primitives.trailing_stop import TrailingStop
    from strategy_framework.primitives.triple_barrier import TripleBarrierConfig


@runtime_checkable
class PnLProtocol(Protocol):
    """PnL calculation contract — used by barrier and reporting mixins."""

    @property
    def net_pnl_pct(self) -> Decimal: ...

    @property
    def net_pnl_quote(self) -> Decimal: ...

    @property
    def cum_fees_quote(self) -> Decimal: ...

    @property
    def trade_pnl_pct(self) -> Decimal: ...


@runtime_checkable
class BarrierControlProtocol(Protocol):
    """Everything MixinBarrierControl needs on self."""

    status: RunnableStatus
    close_type: CloseType | None

    @property
    def net_pnl_pct(self) -> Decimal: ...

    @property
    def triple_barrier(self) -> TripleBarrierConfig: ...

    @property
    def trailing_stop(self) -> TrailingStop | None: ...

    @property
    def elapsed_seconds(self) -> float: ...

    def place_close_order(self, close_type: CloseType) -> None: ...


class RetryProtocol(Protocol):
    """Contract for retry behavior."""

    @property
    def current_retries(self) -> int: ...

    @property
    def max_retries(self) -> int: ...

    def increment_retries(self) -> None: ...


class OrderTrackingProtocol(Protocol):
    """Contract for order tracking behavior."""

    @property
    def open_orders(self) -> list[object]: ...

    @property
    def close_orders(self) -> list[object]: ...

    def update_tracked_order(self, order_id: str, exchange_order_id: str) -> None: ...
