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
class ClockProtocol(Protocol):
    def time(self) -> float:
        """Epoch seconds, same unit as `OrderUpdate.update_timestamp`."""
        ...


@runtime_checkable
class LinkedEventEmitter(Protocol):
    """`EventBusAdapter` satisfies this; keeps linked_orders off hb_compat."""

    def emit(self, event_type: str, payload: object) -> None: ...
