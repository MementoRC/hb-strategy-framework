"""OrderProtocol and TrackedOrderProtocol — contracts for order management."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from decimal import Decimal


@runtime_checkable
class TrackedOrderProtocol(Protocol):
    """Contract for a tracked order object."""

    @property
    def order_id(self) -> str: ...

    @property
    def is_filled(self) -> bool: ...

    @property
    def is_open(self) -> bool: ...

    @property
    def filled_amount(self) -> Decimal: ...

    @property
    def average_price(self) -> Decimal: ...
