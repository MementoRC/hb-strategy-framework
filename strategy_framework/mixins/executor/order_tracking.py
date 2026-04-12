"""OrderTrackingMixin — open/close order list management.

Deliberate redesign from the in-tree version, which only matched order IDs.
This mixin owns the full order list and provides lookup/filtering utilities.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from strategy_framework.protocols.composites import OrderTrackingProtocol
    from strategy_framework.protocols.order import TrackedOrderProtocol


class OrderTrackingMixin:
    """Mixin for managing open and close order lists.

    Usage:
        class MyExecutor(OrderTrackingMixin):
            def __init__(self) -> None:
                self._init_order_tracking()

    MRO init order: call _init_order_tracking() after all super().__init__() calls.
    Calling _init_order_tracking() twice resets lists (safe in diamond MRO).
    """

    def _init_order_tracking(self: OrderTrackingProtocol) -> None:  # type: ignore[misc]
        """Initialize order tracking state. Call from __init__ after super().__init__()."""
        self._open_orders: list[TrackedOrderProtocol] = []  # type: ignore[attr-defined]
        self._close_orders: list[TrackedOrderProtocol] = []  # type: ignore[attr-defined]

    @property
    def open_orders(self: OrderTrackingProtocol) -> list[TrackedOrderProtocol]:  # type: ignore[misc]
        """List of currently open (entry) orders."""
        return self._open_orders  # type: ignore[attr-defined]

    @property
    def close_orders(self: OrderTrackingProtocol) -> list[TrackedOrderProtocol]:  # type: ignore[misc]
        """List of close (exit) orders."""
        return self._close_orders  # type: ignore[attr-defined]

    def add_open_order(
        self: OrderTrackingProtocol,  # type: ignore[misc]
        order: TrackedOrderProtocol,
    ) -> None:
        """Append an open order to the tracking list."""
        self._open_orders.append(order)  # type: ignore[attr-defined]

    def add_close_order(
        self: OrderTrackingProtocol,  # type: ignore[misc]
        order: TrackedOrderProtocol,
    ) -> None:
        """Append a close order to the tracking list."""
        self._close_orders.append(order)  # type: ignore[attr-defined]

    def update_tracked_order(
        self: OrderTrackingProtocol,  # type: ignore[misc]
        order_id: str,
        **kwargs: object,
    ) -> None:
        """Update tracked order state by order_id.

        Base implementation is a no-op. Override in the host to enrich order
        state (e.g., set exchange_order_id, update fill amounts).
        """

    def get_filled_open_orders(
        self: OrderTrackingProtocol,  # type: ignore[misc]
    ) -> list[TrackedOrderProtocol]:
        """Return open orders that are fully filled."""
        return [o for o in self._open_orders if o.is_filled]  # type: ignore[attr-defined]

    def get_open_order(
        self: OrderTrackingProtocol,  # type: ignore[misc]
        order_id: str,
    ) -> TrackedOrderProtocol | None:
        """Return the open order with the given order_id, or None."""
        orders = self._open_orders  # type: ignore[attr-defined]
        return next((o for o in orders if o.order_id == order_id), None)
