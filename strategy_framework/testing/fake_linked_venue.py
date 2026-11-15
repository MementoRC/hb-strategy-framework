"""Test doubles for the linked-order manager: fake venue, codecs, manual clock, emitter."""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Literal

from data_type_primitives import OrderOutcomeUnknownError, OrderState, OrderType, OrderUpdate

from strategy_framework.linked_orders.types import CancelOutcome, LegFill, LegSnapshot

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from data_type_primitives import LegSpec

    from strategy_framework.linked_orders.types import GroupId, LinkTag

PlaceMode = Literal["ok", "unknown", "reject"]
_TERMINAL = frozenset({OrderState.FILLED, OrderState.CANCELED, OrderState.FAILED})
_INT32_MAX = 2**31 - 1


class VenueRejectedError(Exception):
    """A definite placement failure raised by the fake venue."""


class StringLinkIdCodec:
    """`hbl-<group>-<leg>` client-order-id tags."""

    PREFIX = "hbl-"

    def encode(self, group_id: GroupId, leg_index: int) -> LinkTag:
        return f"{self.PREFIX}{group_id}-{leg_index}"

    def decode(self, tag: LinkTag) -> tuple[GroupId, int] | None:
        if not isinstance(tag, str) or not tag.startswith(self.PREFIX):
            return None
        parts = tag[len(self.PREFIX) :].split("-")
        if len(parts) != 2 or not all(p.isdigit() for p in parts):
            return None
        return int(parts[0]), int(parts[1])


class Int32LinkIdCodec:
    """Packs (group, leg) into a non-negative int32 userref: `group << 4 | leg`."""

    LEG_BITS = 4

    def encode(self, group_id: GroupId, leg_index: int) -> LinkTag:
        if group_id < 0 or not 0 <= leg_index < (1 << self.LEG_BITS):
            msg = f"cannot encode group {group_id} leg {leg_index}"
            raise ValueError(msg)
        tag = (group_id << self.LEG_BITS) | leg_index
        if tag > _INT32_MAX:
            msg = f"group {group_id} overflows an int32 userref"
            raise ValueError(msg)
        return tag

    def decode(self, tag: LinkTag) -> tuple[GroupId, int] | None:
        if not isinstance(tag, int) or isinstance(tag, bool) or not 0 <= tag <= _INT32_MAX:
            return None
        return tag >> self.LEG_BITS, tag & ((1 << self.LEG_BITS) - 1)


class ManualClock:
    """Clock advanced by the test."""

    def __init__(self, start: float = 1_000.0) -> None:
        self._now = start

    def time(self) -> float:
        return self._now

    def advance(self, seconds: float) -> float:
        self._now += seconds
        return self._now


class RecordingEmitter:
    """`LinkedEventEmitter` that records everything it is given."""

    def __init__(self) -> None:
        self.events: list[tuple[str, object]] = []

    def emit(self, event_type: str, payload: object) -> None:
        self.events.append((event_type, payload))

    def payloads(self) -> list[object]:
        return [payload for _, payload in self.events]

    def kinds(self) -> list[object]:
        return [getattr(payload, "kind", None) for _, payload in self.events]


@dataclass
class _FakeOrder:
    target: str
    client_order_id: str
    link_tag: LinkTag
    amount: Decimal
    state: OrderState = OrderState.OPEN
    filled: Decimal = Decimal(0)


class FakeEmulationVenue:
    """In-memory `EmulationVenue` with scripted outcomes and controllable reply delay.

    The effect of a call (an order placed, a cancel applied) happens first; only the *reply*
    waits for `release()` when the method is held. That models a slow or lost reply.
    """

    def __init__(self, native_types: Iterable[OrderType] | None = None) -> None:
        self.native_types: frozenset[OrderType] = (
            frozenset(OrderType) if native_types is None else frozenset(native_types)
        )
        self.orders: dict[str, _FakeOrder] = {}
        self.call_log: list[tuple[str, ...]] = []
        self._place: deque[PlaceMode] = deque()
        self._cancel: deque[CancelOutcome] = deque()
        self._get: deque[LegSnapshot | None] = deque()
        self._held: set[str] = set()
        self._gates: dict[str, deque[asyncio.Event]] = defaultdict(deque)
        self._seq = 0

    # -- scripting

    def script_place(self, *modes: PlaceMode) -> None:
        self._place.extend(modes)

    def script_cancel(self, *outcomes: CancelOutcome) -> None:
        self._cancel.extend(outcomes)

    def script_get(self, *answers: LegSnapshot | None) -> None:
        self._get.extend(answers)

    def hold(self, method: str) -> None:
        """Delay replies of `method` ("place_leg", "cancel_leg", "get_leg") until released."""
        self._held.add(method)

    def release(self, method: str, count: int = 1) -> int:
        """Release the oldest `count` delayed replies; returns how many were released."""
        released = 0
        while released < count and self._gates[method]:
            self._gates[method].popleft().set()
            released += 1
        return released

    def release_all(self, method: str) -> int:
        self._held.discard(method)
        return self.release(method, count=len(self._gates[method]))

    def waiting(self, method: str) -> int:
        return len(self._gates[method])

    async def _delay(self, method: str) -> None:
        if method in self._held:
            gate = asyncio.Event()
            self._gates[method].append(gate)
            await gate.wait()

    # -- test helpers (drive the venue side)

    def fill(
        self, client_order_id: str, cumulative: Decimal | int | str, *, fill_id: str | None = None
    ) -> LegFill:
        order = self.orders[client_order_id]
        order.filled = max(order.filled, Decimal(str(cumulative)))
        order.state = (
            OrderState.FILLED if order.filled >= order.amount else OrderState.PARTIALLY_FILLED
        )
        return LegFill(client_order_id, order.filled, Decimal(100), 0.0, fill_id)

    def update(self, client_order_id: str, state: OrderState) -> OrderUpdate:
        order = self.orders[client_order_id]
        order.state = state
        return OrderUpdate(order.target, 0.0, state, client_order_id)

    def snapshot(self, client_order_id: str) -> LegSnapshot:
        order = self.orders[client_order_id]
        return LegSnapshot(client_order_id, order.link_tag, order.state, order.filled)

    def calls(self, method: str) -> list[tuple[str, ...]]:
        return [call for call in self.call_log if call[0] == method]

    # -- EmulationVenue

    def supports_leg(self, target: str, leg: LegSpec) -> bool:
        return leg.order_type in self.native_types

    async def place_leg(self, target: str, leg: LegSpec, *, link_tag: LinkTag) -> str:
        mode: PlaceMode = self._place.popleft() if self._place else "ok"
        self.call_log.append(("place_leg", target, leg.role.value, str(link_tag)))
        if mode == "reject":
            await self._delay("place_leg")
            msg = "venue rejected the order"
            raise VenueRejectedError(msg)
        self._seq += 1
        cid = f"fake-{self._seq}"
        self.orders[cid] = _FakeOrder(target, cid, link_tag, leg.amount)
        await self._delay("place_leg")
        if mode == "unknown":
            msg = "reply lost"
            raise OrderOutcomeUnknownError(msg, client_order_id=cid)
        return cid

    async def cancel_leg(self, target: str, client_order_id: str) -> CancelOutcome:
        self.call_log.append(("cancel_leg", target, client_order_id))
        outcome = self._cancel.popleft() if self._cancel else self._default_cancel(client_order_id)
        order = self.orders.get(client_order_id)
        if order is not None and order.state not in _TERMINAL:
            if outcome is CancelOutcome.CANCELED:
                order.state = OrderState.CANCELED
            elif outcome is CancelOutcome.ALREADY_FILLED:
                order.state, order.filled = OrderState.FILLED, order.amount
        await self._delay("cancel_leg")
        return outcome

    def _default_cancel(self, client_order_id: str) -> CancelOutcome:
        order = self.orders.get(client_order_id)
        if order is None:
            return CancelOutcome.NOT_FOUND
        if order.state is OrderState.FILLED:
            return CancelOutcome.ALREADY_FILLED
        return CancelOutcome.CANCELED

    async def get_leg(
        self,
        target: str,
        *,
        client_order_id: str | None = None,
        link_tag: LinkTag | None = None,
    ) -> LegSnapshot | None:
        if (client_order_id is None) == (link_tag is None):
            msg = "get_leg needs exactly one of client_order_id / link_tag"
            raise ValueError(msg)
        self.call_log.append(("get_leg", target, str(client_order_id or link_tag)))
        answer = self._get.popleft() if self._get else self._lookup(client_order_id, link_tag)
        await self._delay("get_leg")
        return answer

    def _lookup(self, client_order_id: str | None, link_tag: LinkTag | None) -> LegSnapshot | None:
        for order in self.orders.values():
            if order.client_order_id == client_order_id or (
                link_tag is not None and order.link_tag == link_tag
            ):
                return self.snapshot(order.client_order_id)
        return None

    async def list_open_legs(self, target: str) -> Sequence[LegSnapshot]:
        self.call_log.append(("list_open_legs", target))
        await self._delay("list_open_legs")
        return [
            self.snapshot(o.client_order_id)
            for o in self.orders.values()
            if o.target == target and o.state not in _TERMINAL
        ]
