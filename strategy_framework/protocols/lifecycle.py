"""Lifecycle protocols — shutdown and barrier contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from decimal import Decimal

    from strategy_framework.primitives.enums import CloseType


class ShutdownProtocol(Protocol):
    """Contract for graceful shutdown behavior."""

    async def shutdown(self) -> None:  # pragma: no cover
        """Execute graceful shutdown sequence."""
        ...

    @property
    def has_pending_orders(self) -> bool:  # pragma: no cover
        """Whether there are still orders in flight."""
        ...


class BarrierProtocol(Protocol):
    """Contract for barrier evaluation behavior."""

    def evaluate_barriers(  # pragma: no cover
        self, net_pnl_pct: Decimal, elapsed_s: float
    ) -> CloseType | None:
        """Evaluate all barriers, return close type if triggered."""
        ...
