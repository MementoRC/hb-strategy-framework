"""Lifecycle protocols — shutdown and barrier contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from decimal import Decimal

    from strategy_framework.primitives.enums import CloseType


class ShutdownProtocol(Protocol):
    """Contract for graceful shutdown behavior."""

    async def shutdown(self) -> None:
        """Execute graceful shutdown sequence."""
        ...

    @property
    def has_pending_orders(self) -> bool:
        """Whether there are still orders in flight."""
        ...


class BarrierProtocol(Protocol):
    """Contract for barrier evaluation behavior."""

    def evaluate_barriers(self, net_pnl_pct: Decimal, elapsed_s: float) -> CloseType | None:
        """Evaluate all barriers, return close type if triggered."""
        ...
