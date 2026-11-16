"""Errors raised by the linked-order manager (only before the first venue I/O)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from data_type_primitives import LegRole, OrderType

    from strategy_framework.linked_orders.types import GroupId, LinkTag


class LinkedOrderError(Exception):
    """Root of the linked-order error hierarchy."""


class EmulationNotEnabledError(LinkedOrderError):
    """`LinkedOrderManagerConfig.enabled` is False."""

    def __init__(self) -> None:
        super().__init__("emulated linked orders are disabled; set config.enabled=True to opt in")


class VolatileStoreError(LinkedOrderError):
    """The store is not durable and `allow_volatile_store` is False."""

    def __init__(self) -> None:
        super().__init__(
            "linked-group store is not durable; pass a durable store or set allow_volatile_store"
        )


class UnsupportedLegError(LinkedOrderError):
    """The venue cannot place this leg as a native order."""

    def __init__(self, leg_index: int, role: LegRole, order_type: OrderType) -> None:
        super().__init__(f"leg {leg_index} ({role.name}) of type {order_type.name} is unsupported")
        self.leg_index = leg_index
        self.role = role
        self.order_type = order_type


class LinkIdCodecError(LinkedOrderError):
    """The codec cannot encode or round-trip a link tag."""

    def __init__(self, group_id: GroupId, leg_index: int, tag: LinkTag | None) -> None:
        super().__init__(f"codec failed for group {group_id} leg {leg_index} (tag={tag!r})")
        self.group_id = group_id
        self.leg_index = leg_index
        self.tag = tag


class RecoveryRequiredError(LinkedOrderError):
    """`require_recover_before_place` is set and `recover()` has not completed."""

    def __init__(self) -> None:
        super().__init__("recover() must complete before placing linked orders")


class GroupIdPersistenceError(LinkedOrderError):
    """The group-id high-water mark could not be saved; nothing was placed (fail closed)."""

    def __init__(self, group_id: GroupId) -> None:
        super().__init__(f"could not persist group id high-water mark {group_id}; not placing")
        self.group_id = group_id


class GroupInvariantError(LinkedOrderError):
    """An internal invariant of a linked group was violated (a bug, not a caller error)."""

    def __init__(self, group_id: GroupId, detail: str) -> None:
        super().__init__(f"linked group {group_id} invariant violated: {detail}")
        self.group_id = group_id


class LinkedGroupNotFoundError(LinkedOrderError):
    """No group with this id is known."""

    def __init__(self, group_id: str) -> None:
        super().__init__(f"unknown linked group {group_id!r}")
        self.group_id = group_id
