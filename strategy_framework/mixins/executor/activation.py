"""ActivationBoundsMixin — activation price bounds check.

Deliberate redesign from the in-tree version:
- Caller provides current_price (no internal market call)
- Pure function — no state, no _init_ needed
- Side/order-type asymmetry dropped (callers needing this can subclass)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from decimal import Decimal

    from strategy_framework.protocols.composites import ActivationBoundsProtocol


class ActivationBoundsMixin:
    """Mixin for checking if market price is within activation bounds.

    Usage:
        class MyExecutor(ActivationBoundsMixin):
            entry_price: Decimal = Decimal("100")
            activation_bounds: tuple[Decimal, Decimal] | None = (
                Decimal("0.99"), Decimal("1.01")
            )

        # In control loop:
        mid = self.market.get_mid_price()
        if self.is_within_activation_bounds(mid):
            self._activate()

    No state, no _init_ required.
    """

    def is_within_activation_bounds(
        self: ActivationBoundsProtocol,
        current_price: Decimal,
    ) -> bool:
        """Return True if current_price is within activation bounds.

        If activation_bounds is None, always returns True (always active).
        Bounds are (lower_multiplier, upper_multiplier) relative to entry_price:
            active when entry_price * lower <= current_price <= entry_price * upper
        """
        if self.activation_bounds is None:
            return True
        lower_mult, upper_mult = self.activation_bounds
        lower = self.entry_price * lower_mult
        upper = self.entry_price * upper_mult
        return lower <= current_price <= upper
