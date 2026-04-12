"""BalanceValidationMixin — balance check before order placement.

STUB: raises NotImplementedError. Implement when a market adapter providing
MarketAccessProtocol.get_available_balance() exists (hb-market-simulator or
live-market sub-package).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from decimal import Decimal

    from strategy_framework.protocols.market import MarketAccessProtocol


class BalanceValidationMixin:
    """Stub mixin for pre-order balance validation.

    Will be implemented once hb-market-simulator or a live-market sub-package
    provides a concrete MarketAccessProtocol.get_available_balance() adapter.
    """

    def validate_balance(
        self: MarketAccessProtocol,
        currency: str,
        amount: Decimal,
    ) -> bool:
        """Return True if sufficient balance is available.

        STUB — not yet implemented.
        """
        raise NotImplementedError(
            "BalanceValidationMixin.validate_balance requires a concrete market "
            "adapter implementing MarketAccessProtocol.get_available_balance(). "
            "See hb-market-simulator BalanceProtocol for the expected interface. "
            "Implement this when hb-market-simulator or live-market sub-package "
            "provides the adapter."
        )
