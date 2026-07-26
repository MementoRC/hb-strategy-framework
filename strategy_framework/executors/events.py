from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from decimal import Decimal


@dataclass(frozen=True)
class OrderFilledEvent:
    order_id: str
    price: Decimal
    amount: Decimal


@dataclass(frozen=True)
class OrderCancelledEvent:
    order_id: str


@dataclass(frozen=True)
class OrderFailedEvent:
    order_id: str
    reason: str


@dataclass(frozen=True)
class PriceUpdatedEvent:
    price: Decimal
