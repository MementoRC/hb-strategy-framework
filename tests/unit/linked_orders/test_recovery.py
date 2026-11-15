"""Tests I: restart recovery reconciles the store and the venue in both directions."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from decimal import Decimal
from typing import TYPE_CHECKING

from data_type_primitives import OrderState

from strategy_framework.linked_orders.config import LinkedOrderManagerConfig
from strategy_framework.linked_orders.events import LinkedEventKind as K
from strategy_framework.linked_orders.types import DegradedReason as R
from strategy_framework.linked_orders.types import GroupState as S
from strategy_framework.linked_orders.types import LegStatus
from tests.unit.linked_orders.builders import bracket_spec, oco_spec
from tests.unit.linked_orders.manager_helpers import (
    TARGET,
    SpyStore,
    events,
    leg,
    make_manager,
    record,
    spawn,
    spin,
)

if TYPE_CHECKING:
    import pytest

    from strategy_framework.linked_orders.manager import EmulatedLinkedOrderManager
    from strategy_framework.linked_orders.types import LegSnapshot
    from strategy_framework.testing.fake_linked_venue import (
        FakeEmulationVenue,
        ManualClock,
        RecordingEmitter,
        StringLinkIdCodec,
    )

D = Decimal
LS = LegStatus


def restart(
    venue: FakeEmulationVenue,
    codec: StringLinkIdCodec,
    clock: ManualClock,
    store: SpyStore,
    emitter: RecordingEmitter | None = None,
    config: LinkedOrderManagerConfig | None = None,
) -> EmulatedLinkedOrderManager:
    cfg = config or LinkedOrderManagerConfig(enabled=True)
    return make_manager(venue, codec, clock, emitter, store, cfg)


async def test_consistent_state_resumes_armed_and_seeds_the_counter(
    manager: EmulatedLinkedOrderManager,
    venue: FakeEmulationVenue,
    codec: StringLinkIdCodec,
    clock: ManualClock,
    durable_store: SpyStore,
    emitter: RecordingEmitter,
) -> None:
    await manager.place_oco(TARGET, oco_spec())
    fresh = restart(venue, codec, clock, durable_store, emitter)
    await fresh.recover([TARGET])
    assert fresh.get_handle("1").state is S.ARMED
    assert leg(fresh, 0).unresolved_since is None
    handle = await fresh.place_oco(TARGET, oco_spec())
    assert handle.state is S.ARMED
    assert [c[3] for c in venue.calls("place_leg")][-2:] == ["hbl-2-0", "hbl-2-1"]
    recovered = events(emitter, K.RECOVERED)
    assert len(recovered) == 1
    assert "groups=1" in recovered[0].detail


async def test_write_ahead_leg_without_id_is_adopted_by_tag(
    manager: EmulatedLinkedOrderManager,
    venue: FakeEmulationVenue,
    codec: StringLinkIdCodec,
    clock: ManualClock,
    durable_store: SpyStore,
) -> None:
    venue.hold("place_leg")
    task = spawn(manager.place_oco(TARGET, oco_spec()))
    await spin()
    task.cancel()  # crash: the reply never arrives
    await asyncio.gather(task, return_exceptions=True)
    assert durable_store.load_all()[0].legs[0].client_order_id is None
    venue.release_all("place_leg")
    fresh = restart(venue, codec, clock, durable_store)
    await fresh.recover([TARGET])
    assert leg(fresh, 0).client_order_id == "fake-1"
    assert leg(fresh, 0).status is LS.OPEN
    # the missing second leg had no write-ahead record: it is submitted now
    assert fresh.get_handle("1").state is S.ARMED
    assert [c[3] for c in venue.calls("place_leg")] == ["hbl-1-0", "hbl-1-1"]


async def test_tag_not_found_stays_unresolved_never_replaced_and_degrades_after_grace(
    manager: EmulatedLinkedOrderManager,
    venue: FakeEmulationVenue,
    codec: StringLinkIdCodec,
    clock: ManualClock,
    durable_store: SpyStore,
    emitter: RecordingEmitter,
) -> None:
    venue.hold("place_leg")
    task = spawn(manager.place_oco(TARGET, oco_spec()))
    await spin()
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    venue.release_all("place_leg")
    venue.update("fake-1", OrderState.CANCELED)  # closed on the venue: not in the open list
    fresh = restart(venue, codec, clock, durable_store, emitter)
    venue.script_get(None)  # the venue cannot look up by tag
    await fresh.recover([TARGET])
    assert leg(fresh, 0).client_order_id is None
    assert leg(fresh, 0).unresolved_since == clock.time()
    assert [c[3] for c in venue.calls("place_leg")].count("hbl-1-0") == 1  # never re-submitted
    clock.advance(31)
    venue.script_get(None)
    await fresh.tick()
    assert record(fresh).state is S.DEGRADED
    assert [e.reason for e in events(emitter, K.DEGRADED)] == [R.UNRESOLVED_PAST_GRACE]
    assert [c[3] for c in venue.calls("place_leg")].count("hbl-1-0") == 1


async def test_tick_adopts_a_tagged_leg_once_the_venue_can_find_it(
    manager: EmulatedLinkedOrderManager,
    venue: FakeEmulationVenue,
    codec: StringLinkIdCodec,
    clock: ManualClock,
    durable_store: SpyStore,
) -> None:
    venue.hold("place_leg")
    task = spawn(manager.place_oco(TARGET, oco_spec()))
    await spin()
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    venue.release_all("place_leg")
    venue.update("fake-1", OrderState.CANCELED)
    fresh = restart(venue, codec, clock, durable_store)
    venue.script_get(None)
    await fresh.recover([TARGET])
    assert leg(fresh, 0).client_order_id is None
    await fresh.tick()  # the lookup by tag now succeeds
    assert leg(fresh, 0).client_order_id == "fake-1"
    assert leg(fresh, 0).status is LS.CANCELED


async def test_leg_filled_while_down_cancels_the_sibling(
    manager: EmulatedLinkedOrderManager,
    venue: FakeEmulationVenue,
    codec: StringLinkIdCodec,
    clock: ManualClock,
    durable_store: SpyStore,
) -> None:
    await manager.place_oco(TARGET, oco_spec())
    venue.fill("fake-1", 1)  # filled while the process was down
    fresh = restart(venue, codec, clock, durable_store)
    await fresh.recover([TARGET])
    assert [c[2] for c in venue.calls("cancel_leg")] == ["fake-2"]
    assert fresh.get_handle("1").state is S.COMPLETED


async def test_both_legs_filled_while_down_is_double_fill(
    manager: EmulatedLinkedOrderManager,
    venue: FakeEmulationVenue,
    codec: StringLinkIdCodec,
    clock: ManualClock,
    durable_store: SpyStore,
    emitter: RecordingEmitter,
) -> None:
    await manager.place_oco(TARGET, oco_spec())
    venue.fill("fake-1", 1)
    venue.fill("fake-2", 1)
    fresh = restart(venue, codec, clock, durable_store, emitter)
    await fresh.recover([TARGET])
    assert fresh.get_handle("1").state is S.DEGRADED
    assert [e.reason for e in events(emitter, K.DEGRADED)] == [R.DOUBLE_FILL]
    assert venue.calls("cancel_leg") == []


async def test_partial_entry_still_open_resumes_entry_working(
    manager: EmulatedLinkedOrderManager,
    venue: FakeEmulationVenue,
    codec: StringLinkIdCodec,
    clock: ManualClock,
    durable_store: SpyStore,
) -> None:
    await manager.place_bracket(TARGET, bracket_spec())
    venue.fill("fake-1", 1)
    fresh = restart(venue, codec, clock, durable_store)
    await fresh.recover([TARGET])
    assert fresh.get_handle("1").state is S.ENTRY_WORKING
    assert leg(fresh, 0).filled == D(1)
    assert len(venue.calls("place_leg")) == 1


async def test_bracket_entry_done_while_down_places_the_exits(
    manager: EmulatedLinkedOrderManager,
    venue: FakeEmulationVenue,
    codec: StringLinkIdCodec,
    clock: ManualClock,
    durable_store: SpyStore,
) -> None:
    await manager.place_bracket(TARGET, bracket_spec())
    venue.fill("fake-1", 2)
    fresh = restart(venue, codec, clock, durable_store)
    await fresh.recover([TARGET])
    assert fresh.get_handle("1").state is S.ARMED
    assert len(venue.calls("place_leg")) == 3


async def test_conflicting_id_at_a_leg_index_is_link_broken(
    manager: EmulatedLinkedOrderManager,
    venue: FakeEmulationVenue,
    codec: StringLinkIdCodec,
    clock: ManualClock,
    durable_store: SpyStore,
    emitter: RecordingEmitter,
) -> None:
    await manager.place_oco(TARGET, oco_spec())
    stored = durable_store.load_all()[0]
    legs = (replace(stored.legs[0], client_order_id="other"), stored.legs[1])
    durable_store.save(replace(stored, legs=legs))
    fresh = restart(venue, codec, clock, durable_store, emitter)
    await fresh.recover([TARGET])
    assert R.LINK_BROKEN in record(fresh).degraded_reasons
    assert [e.reason for e in events(emitter, K.DEGRADED)].count(R.LINK_BROKEN) == 1


async def test_orphans_are_reported_and_left_alone(
    manager: EmulatedLinkedOrderManager,
    venue: FakeEmulationVenue,
    codec: StringLinkIdCodec,
    clock: ManualClock,
    emitter: RecordingEmitter,
) -> None:
    await manager.place_oco(TARGET, oco_spec())
    await venue.place_leg(TARGET, oco_spec().legs[0], link_tag="not-ours")  # undecodable
    await venue.place_leg(TARGET, oco_spec().legs[0], link_tag=12345)  # undecodable
    fresh = restart(venue, codec, clock, SpyStore(), emitter)
    await fresh.recover([TARGET])
    orphans = events(emitter, K.ORPHAN_FOUND)
    assert [e.group_id for e in orphans] == ["1", "1"]
    assert venue.calls("cancel_leg") == []
    handle = await fresh.place_oco(TARGET, oco_spec())  # counter seeded past the orphan
    assert [c[3] for c in venue.calls("place_leg")][-2:] == ["hbl-2-0", "hbl-2-1"]
    assert handle.state is S.ARMED
    assert "orphans=1" in events(emitter, K.RECOVERED)[0].detail


async def test_orphans_are_cancelled_when_configured(
    manager: EmulatedLinkedOrderManager,
    venue: FakeEmulationVenue,
    codec: StringLinkIdCodec,
    clock: ManualClock,
) -> None:
    await manager.place_oco(TARGET, oco_spec())
    config = LinkedOrderManagerConfig(enabled=True, cancel_orphans=True)
    fresh = restart(venue, codec, clock, SpyStore(), config=config)
    await fresh.recover([TARGET])
    assert sorted(c[2] for c in venue.calls("cancel_leg")) == ["fake-1", "fake-2"]


async def _boom(*_a: object, **_k: object) -> object:
    raise RuntimeError


async def test_list_open_failure_is_tolerated(
    manager: EmulatedLinkedOrderManager,
    venue: FakeEmulationVenue,
    codec: StringLinkIdCodec,
    clock: ManualClock,
    durable_store: SpyStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await manager.place_oco(TARGET, oco_spec())
    monkeypatch.setattr(venue, "list_open_legs", _boom)
    fresh = restart(venue, codec, clock, durable_store)
    await fresh.recover([TARGET])
    assert fresh.get_handle("1").state is S.ARMED


def _negative_open_list(venue: FakeEmulationVenue, monkeypatch: pytest.MonkeyPatch) -> None:
    async def negative(_target: str) -> list[LegSnapshot]:
        return [replace(venue.snapshot(cid), filled=D(-1)) for cid in ("fake-1", "fake-2")]

    monkeypatch.setattr(venue, "list_open_legs", negative)


async def test_negative_fill_in_open_list_is_no_information_not_an_orphan(
    manager: EmulatedLinkedOrderManager,
    venue: FakeEmulationVenue,
    codec: StringLinkIdCodec,
    clock: ManualClock,
    emitter: RecordingEmitter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await manager.place_oco(TARGET, oco_spec())
    _negative_open_list(venue, monkeypatch)
    config = LinkedOrderManagerConfig(enabled=True, cancel_orphans=True)
    fresh = restart(venue, codec, clock, SpyStore(), emitter, config)
    await fresh.recover([TARGET])
    assert events(emitter, K.ORPHAN_FOUND) == []
    assert venue.calls("cancel_leg") == []
    handle = await fresh.place_oco(TARGET, oco_spec())  # id counter still seeded past the group
    assert [c[3] for c in venue.calls("place_leg")][-2:] == ["hbl-2-0", "hbl-2-1"]
    assert handle.state is S.ARMED


async def test_negative_fill_in_open_list_does_not_touch_a_stored_group(
    manager: EmulatedLinkedOrderManager,
    venue: FakeEmulationVenue,
    codec: StringLinkIdCodec,
    clock: ManualClock,
    durable_store: SpyStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await manager.place_oco(TARGET, oco_spec())
    stored = durable_store.load_all()[0]
    legs = (replace(stored.legs[0], client_order_id="other"), stored.legs[1])
    durable_store.save(replace(stored, legs=legs))
    _negative_open_list(venue, monkeypatch)
    fresh = restart(venue, codec, clock, durable_store)
    await fresh.recover([TARGET])
    assert R.LINK_BROKEN not in record(fresh).degraded_reasons
    assert leg(fresh, 1).filled == D(0)
    assert venue.calls("cancel_leg") == []


async def test_orphan_cancel_failure_is_tolerated(
    manager: EmulatedLinkedOrderManager,
    venue: FakeEmulationVenue,
    codec: StringLinkIdCodec,
    clock: ManualClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await manager.place_oco(TARGET, oco_spec())
    monkeypatch.setattr(venue, "cancel_leg", _boom)
    config = LinkedOrderManagerConfig(enabled=True, cancel_orphans=True)
    fresh = restart(venue, codec, clock, SpyStore(), config=config)
    await fresh.recover([TARGET])  # logged, not raised


async def test_tombstone_group_is_purged_with_its_ids(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue, clock: ManualClock
) -> None:
    await manager.place_oco(TARGET, oco_spec())
    await manager.on_fill(venue.fill("fake-1", 1))
    clock.advance(10)
    await manager.tick()
    assert 1 in manager._groups  # noqa: SLF001
    clock.advance(300)
    await manager.tick()
    assert 1 not in manager._groups  # noqa: SLF001
    assert "fake-1" not in manager._by_cid  # noqa: SLF001
