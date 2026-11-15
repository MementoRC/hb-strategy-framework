"""The single event type emitted by the linked-order manager."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from decimal import Decimal

    from data_type_primitives import LinkKind

    from strategy_framework.linked_orders.types import DegradedReason, GroupState

LINKED_GROUP_EVENT = "linked.group"


class LinkedEventKind(Enum):
    PLACED = "placed"
    LEG_UPDATED = "leg_updated"
    TRIGGERED = "triggered"
    COMPLETED = "completed"
    CANCELED = "canceled"
    FAILED = "failed"
    DEGRADED = "degraded"
    CLOSED = "closed"
    ORPHAN_FOUND = "orphan_found"
    RECOVERED = "recovered"
    SHUTDOWN_OPEN = "shutdown_open"


@dataclass(frozen=True)
class LinkedGroupEvent:
    """Payload of the `"linked.group"` event."""

    kind: LinkedEventKind
    group_id: str
    link_kind: LinkKind | None
    target: str
    state: GroupState | None
    timestamp: float
    leg_index: int | None = None
    client_order_ids: tuple[str | None, ...] = ()
    filled: tuple[Decimal, ...] = ()
    reason: DegradedReason | None = None
    deferred: bool = False
    residual_filled: Decimal | None = None
    detail: str = ""
