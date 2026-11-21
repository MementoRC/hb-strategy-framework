"""Manager-level behaviour of the unresolved-leg backoff (review of #97, issue #95)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from data_type_primitives import OrderState

from strategy_framework.linked_orders.types import LegStatus
from tests.unit.linked_orders.builders import oco_spec
from tests.unit.linked_orders.manager_helpers import (
    TARGET,
    SpyStore,
    leg,
    make_manager,
    spawn,
    spin,
)

if TYPE_CHECKING:
    from strategy_framework.linked_orders.manager import EmulatedLinkedOrderManager
    from strategy_framework.testing.fake_linked_venue import (
        FakeEmulationVenue,
        ManualClock,
        StringLinkIdCodec,
    )


def _gets(venue: FakeEmulationVenue) -> int:
    return len(venue.calls("get_leg"))


async def test_store_never_sees_transient_retry_fields(
    manager: EmulatedLinkedOrderManager,
    venue: FakeEmulationVenue,
    clock: ManualClock,
    durable_store: SpyStore,
) -> None:
    venue.script_place("ok", "unknown")
    await manager.place_oco(TARGET, oco_spec())
    venue.script_get(None)
    clock.advance(1.0)
    await manager.tick()
    assert leg(manager, 1).retry_at is not None
    await manager.on_fill(venue.fill("fake-1", 1))  # a durable change while retry state is set
    await manager.shutdown()
    legs = [leg_rec for saved in durable_store.saves for leg_rec in saved.legs]
    assert all(leg_rec.retry_at is None and leg_rec.retry_delay_s is None for leg_rec in legs)
    assert leg(manager, 1).retry_at is not None  # the in-memory record keeps its schedule


async def _tag_only_leg_manager(
    manager: EmulatedLinkedOrderManager,
    venue: FakeEmulationVenue,
    codec: StringLinkIdCodec,
    clock: ManualClock,
    durable_store: SpyStore,
) -> EmulatedLinkedOrderManager:
    """A recovered group whose leg 0 has no client order id and cannot be found by tag."""
    venue.hold("place_leg")
    task = spawn(manager.place_oco(TARGET, oco_spec()))
    await spin()
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    venue.release_all("place_leg")
    venue.update("fake-1", OrderState.CANCELED)
    fresh = make_manager(venue, codec, clock, None, durable_store)
    venue.script_get(*[None] * 20)
    await fresh.recover([TARGET])
    assert leg(fresh, 0).client_order_id is None
    assert leg(fresh, 0).status in {LegStatus.PENDING_CREATE, LegStatus.UNKNOWN}
    return fresh


async def test_tag_lookups_follow_the_same_backoff(
    manager: EmulatedLinkedOrderManager,
    venue: FakeEmulationVenue,
    codec: StringLinkIdCodec,
    clock: ManualClock,
    durable_store: SpyStore,
) -> None:
    fresh = await _tag_only_leg_manager(manager, venue, codec, clock, durable_store)
    base = _gets(venue)
    await fresh.tick()
    clock.advance(0.5)
    await fresh.tick()
    assert _gets(venue) == base  # nothing before base_s has elapsed
    clock.advance(0.5)
    await fresh.tick()
    assert _gets(venue) == base + 1
    clock.advance(1.0)
    await fresh.tick()
    assert _gets(venue) == base + 1  # next gap is 2s
    clock.advance(1.0)
    await fresh.tick()
    assert _gets(venue) == base + 2


async def test_slow_get_leg_is_not_overlapped_by_the_next_retry(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue, clock: ManualClock
) -> None:
    venue.script_place("ok", "unknown")
    await manager.place_oco(TARGET, oco_spec())
    venue.script_get(None, None, None)
    venue.hold("get_leg")
    clock.advance(1.0)
    first = spawn(manager.tick())
    await spin()
    assert venue.waiting("get_leg") == 1
    clock.advance(2.0)  # the next retry is due while the first lookup is still pending
    second = spawn(manager.tick())
    await spin()
    assert venue.waiting("get_leg") == 1
    assert _gets(venue) == 1
    venue.release_all("get_leg")
    await asyncio.gather(first, second)
    clock.advance(4.0)  # the guard is cleared on completion: the next retry goes out
    await manager.tick()
    assert _gets(venue) == 2
