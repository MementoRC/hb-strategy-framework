"""Protocols injected into the linked-order manager.

Venue I/O is async (it awaits a real outcome and may raise `OrderOutcomeUnknownError`);
codec, store, clock and emitter are sync.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence

    from data_type_primitives import LegSpec

    from strategy_framework.linked_orders.types import (
        CancelOutcome,
        GroupId,
        GroupRecord,
        LegSnapshot,
        LinkTag,
    )


@runtime_checkable
class LinkedOrderIdCodec(Protocol):
    """Maps (group, leg_index) to the tag the venue attaches to the order.

    `leg_index` is the position in `spec.ordered_legs()`.
    """

    def encode(self, group_id: GroupId, leg_index: int) -> LinkTag: ...

    def decode(self, tag: LinkTag) -> tuple[GroupId, int] | None: ...


@runtime_checkable
class BoundedLinkIdCodec(Protocol):
    """Optional codec capability: the largest encodable GroupId, inclusive (e.g. int32 layouts).

    Detected with `isinstance`. The manager raises `GroupIdSpaceExhaustedError` instead of
    allocating an id above this; ids are never clamped or wrapped.
    """

    @property
    def max_group_id(self) -> GroupId: ...


@runtime_checkable
class EmulationVenue(Protocol):
    """Native single-order venue operations used to emulate the link."""

    def supports_leg(self, target: str, leg: LegSpec) -> bool:
        """True if the venue can place this leg as a native, server-side order."""
        ...

    async def place_leg(self, target: str, leg: LegSpec, *, link_tag: LinkTag) -> str:
        """Return the client_order_id. MUST attach `link_tag`.

        A lost reply raises `OrderOutcomeUnknownError` (with `.client_order_id`); any other
        exception means the order was definitely not placed.
        """
        ...

    async def cancel_leg(self, target: str, client_order_id: str) -> CancelOutcome: ...

    async def get_leg(
        self,
        target: str,
        *,
        client_order_id: str | None = None,
        link_tag: LinkTag | None = None,
    ) -> LegSnapshot | None:
        """Look up by exactly one key. None means no record (NOT proof of non-placement)."""
        ...

    async def list_open_legs(self, target: str) -> Sequence[LegSnapshot]: ...


@runtime_checkable
class LinkedGroupStore(Protocol):
    """Group persistence. A durable store is required unless explicitly waived."""

    @property
    def durable(self) -> bool: ...

    def save(self, record: GroupRecord) -> None:
        """Upsert; must be durable before returning."""
        ...

    def load_all(self) -> Sequence[GroupRecord]: ...

    def delete(self, group_id: GroupId) -> None: ...


@runtime_checkable
class GroupIdHighWaterStore(Protocol):
    """Optional store capability: the highest group id ever allocated, kept across restarts.

    Group ids must never repeat on an account. Some venues reject a duplicate client order id only
    among OPEN orders (e.g. Kraken `cl_ord_id`), and even then a lookup by client id can match an
    older CLOSED order and misattribute its state or fills. A store that can persist this survives
    a wiped group table. Detected with `isinstance`.
    """

    def load_group_id_hwm(self) -> GroupId | None:
        """The highest group id ever saved, or None if none was."""
        ...

    def save_group_id_hwm(self, group_id: GroupId) -> None:
        """Must be durable before returning."""
        ...


@runtime_checkable
class GroupIdAllocator(Protocol):
    """Injected source of group ids, shared by managers (processes, hosts) on one account.

    Async because a real implementation takes a cross-process lock and does durable I/O.
    """

    async def reserve_group_id(self) -> GroupId:
        """Atomic and durable before return; never returns the same value twice in its scope.

        May leave gaps. Raises on exhaustion or failure (the manager then fails closed).
        """
        ...


@runtime_checkable
class ClockProtocol(Protocol):
    def time(self) -> float:
        """Epoch seconds, same unit as `OrderUpdate.update_timestamp`."""
        ...


@runtime_checkable
class LinkedEventEmitter(Protocol):
    """`EventBusAdapter` satisfies this; keeps linked_orders off hb_compat."""

    def emit(self, event_type: str, payload: object) -> None: ...
