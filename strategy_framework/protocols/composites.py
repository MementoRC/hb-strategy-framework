"""Pre-built composite protocol joins for common mixin requirements.

These combine simple protocols into the exact interface a specific mixin needs.
Mixin methods type `self:` against these composites.

Convention:
- *HostProtocol  — what the HOST must provide (mixin reads these as inputs)
- *Protocol      — what CONSUMERS see on a class that has the mixin (output contract)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from decimal import Decimal

    from strategy_framework.hb_compat.common import TradeType
    from strategy_framework.primitives.enums import CloseType, RunnableStatus
    from strategy_framework.primitives.trailing_stop import TrailingStop
    from strategy_framework.primitives.triple_barrier import TripleBarrierConfig


# ---------------------------------------------------------------------------
# PNL
# ---------------------------------------------------------------------------


class PnLHostProtocol(Protocol):
    """What the host must provide for PNLCalculatorMixin to compute PnL."""

    @property
    def entry_price(self) -> Decimal: ...

    @property
    def close_price(self) -> Decimal: ...

    @property
    def open_filled_amount_quote(self) -> Decimal: ...

    @property
    def trade_side(self) -> TradeType: ...

    @property
    def cum_fees_raw(self) -> Decimal: ...


@runtime_checkable
class PnLProtocol(Protocol):
    """PnL output contract — what consumers see on a class with PNLCalculatorMixin."""

    @property
    def net_pnl_pct(self) -> Decimal: ...

    @property
    def net_pnl_quote(self) -> Decimal: ...

    @property
    def cum_fees_quote(self) -> Decimal: ...

    @property
    def trade_pnl_pct(self) -> Decimal: ...

    @property
    def trade_pnl_quote(self) -> Decimal: ...


# ---------------------------------------------------------------------------
# Barrier / TrailingStop
# ---------------------------------------------------------------------------


@runtime_checkable
class BarrierControlProtocol(Protocol):
    """Host protocol for TrailingStopMixin and barrier evaluation."""

    status: RunnableStatus
    close_type: CloseType | None

    @property
    def net_pnl_pct(self) -> Decimal: ...  # satisfied by PNLCalculatorMixin

    @property
    def triple_barrier(self) -> TripleBarrierConfig: ...

    @property
    def trailing_stop(self) -> TrailingStop | None: ...

    @property
    def elapsed_seconds(self) -> float: ...

    def place_close_order(self, close_type: CloseType) -> None: ...


# ---------------------------------------------------------------------------
# Retry
# ---------------------------------------------------------------------------


class RetryHostProtocol(Protocol):
    """What the host must provide for RetryMixin (input contract)."""

    max_retries: int


@runtime_checkable
class RetryProtocol(Protocol):
    """Retry output contract — what consumers see on a class with RetryMixin."""

    current_retries: int  # plain attribute — NOTE: runtime_checkable does NOT verify data attrs
    max_retries: int

    def increment_retries(self) -> None: ...


# ---------------------------------------------------------------------------
# OrderTracking
# ---------------------------------------------------------------------------


@runtime_checkable
class OrderTrackingProtocol(Protocol):
    """Order tracking output contract."""

    @property
    def open_orders(self) -> list[object]: ...

    @property
    def close_orders(self) -> list[object]: ...

    def update_tracked_order(self, order_id: str, **kwargs: object) -> None: ...


# ---------------------------------------------------------------------------
# ActivationBounds
# ---------------------------------------------------------------------------


@runtime_checkable
class ActivationBoundsProtocol(Protocol):
    """Host protocol for ActivationBoundsMixin."""

    entry_price: Decimal
    activation_bounds: tuple[Decimal, Decimal] | None
    # Bounds semantics: (lower_multiplier, upper_multiplier) relative to entry_price.
    # Example: (Decimal("0.99"), Decimal("1.01")) = active when price within 1% of entry.
    # None = always active.
