"""Tests G (BRACKET): the entry first, exits once the entry is done and its fill confirmed."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from data_type_primitives import OrderState

from strategy_framework.linked_orders.events import LinkedEventKind as K
from strategy_framework.linked_orders.types import BracketHandle, LegStatus
from strategy_framework.linked_orders.types import DegradedReason as R
from strategy_framework.linked_orders.types import GroupState as S
from tests.unit.linked_orders.builders import bracket_spec
from tests.unit.linked_orders.manager_helpers import (
    TARGET,
    SpyStore,
    assert_write_ahead,
    events,
    leg,
    record,
    spawn,
    spin,
)

if TYPE_CHECKING:
    from strategy_framework.linked_orders.manager import EmulatedLinkedOrderManager
    from strategy_framework.testing.fake_linked_venue import (
        FakeEmulationVenue,
        RecordingEmitter,
    )

D = Decimal
OS = OrderState
LS = LegStatus


async def test_entry_is_placed_alone(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue
) -> None:
    handle = await manager.place_bracket(TARGET, bracket_spec())
    assert handle.state is S.ENTRY_WORKING
    assert handle.entry_client_order_id == "fake-1"
    assert handle.take_profit_client_order_id is None
    assert handle.stop_loss_client_order_id is None
    assert len(venue.calls("place_leg")) == 1


async def test_partial_entry_fill_only_updates_the_leg(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue, emitter: RecordingEmitter
) -> None:
    await manager.place_bracket(TARGET, bracket_spec())
    await manager.on_fill(venue.fill("fake-1", 1))
    assert record(manager).state is S.ENTRY_WORKING  # the unprotected window
    assert leg(manager, 0).filled == D(1)
    assert K.LEG_UPDATED in emitter.kinds()
    assert len(venue.calls("place_leg")) == 1


async def test_entry_filled_waits_for_get_leg_then_places_exits(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue
) -> None:
    await manager.place_bracket(TARGET, bracket_spec())
    venue.script_get(None)  # the first confirmation has no answer
    venue.fill("fake-1", 2)  # venue-side state only
    await manager.on_order_update(venue.update("fake-1", OS.FILLED))
    assert record(manager).state is S.ENTRY_WORKING  # filled == 0 locally: unconfirmed
    assert len(venue.calls("place_leg")) == 1
    await manager.tick()  # get_leg now answers with filled == 2
    assert record(manager).state is S.ARMED
    assert [leg(manager, i).placed_amount for i in (1, 2)] == [D(2), D(2)]
    handle = manager.get_handle("1")
    assert isinstance(handle, BracketHandle)
    assert (handle.take_profit_client_order_id, handle.stop_loss_client_order_id) == (
        "fake-2",
        "fake-3",
    )
    assert_write_ahead(venue.call_log)


async def test_canceled_entry_with_partial_fill_sizes_exits_to_the_partial(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue
) -> None:
    await manager.place_bracket(TARGET, bracket_spec())
    await manager.on_fill(venue.fill("fake-1", 1))
    await manager.on_order_update(venue.update("fake-1", OS.CANCELED))
    assert record(manager).state is S.ARMED
    assert venue.orders["fake-2"].amount == D(1)
    assert venue.orders["fake-3"].amount == D(1)


async def test_zero_fill_canceled_and_failed_entries(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue, emitter: RecordingEmitter
) -> None:
    await manager.place_bracket(TARGET, bracket_spec())
    await manager.on_order_update(venue.update("fake-1", OS.CANCELED))
    assert manager.get_handle("1").state is S.CANCELED
    await manager.place_bracket(TARGET, bracket_spec())
    await manager.on_order_update(venue.update("fake-2", OS.FAILED))
    assert manager.get_handle("2").state is S.FAILED
    assert len(venue.calls("place_leg")) == 2
    assert K.CANCELED in emitter.kinds()
    assert K.FAILED in emitter.kinds()


async def test_entry_rejected_fails_the_group(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue
) -> None:
    venue.script_place("reject")
    handle = await manager.place_bracket(TARGET, bracket_spec())
    assert handle.state is S.FAILED
    assert handle.entry_client_order_id is None


async def test_single_exit_bracket_completes_on_its_fill(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue, durable_store: SpyStore
) -> None:
    await manager.place_bracket(TARGET, bracket_spec(stop_loss=False))
    await manager.on_fill(venue.fill("fake-1", 2))
    await manager.on_order_update(venue.update("fake-1", OS.FILLED))
    assert record(manager).state is S.ARMED
    assert len(venue.calls("place_leg")) == 2
    await manager.on_fill(venue.fill("fake-2", 2))
    assert manager.get_handle("1").state is S.COMPLETED
    assert durable_store.load_all() == []  # entry and exit are terminal: closed


async def test_exit_rejected_degrades_without_retry_and_other_exit_is_still_placed(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue, emitter: RecordingEmitter
) -> None:
    venue.script_place("ok", "reject", "ok")
    await manager.place_bracket(TARGET, bracket_spec())
    await manager.on_fill(venue.fill("fake-1", 1))
    await manager.on_order_update(venue.update("fake-1", OS.CANCELED))
    handle = manager.get_handle("1")
    assert isinstance(handle, BracketHandle)
    assert handle.state is S.DEGRADED
    assert handle.take_profit_client_order_id is None
    assert handle.stop_loss_client_order_id == "fake-2"  # protection wins
    assert len(venue.calls("place_leg")) == 3  # entry, rejected TP, SL: no retry
    degraded = events(emitter, K.DEGRADED)
    assert [e.reason for e in degraded] == [R.EXIT_PLACEMENT_FAILED]
    assert "unprotected" in degraded[0].detail
    # the surviving exit still triggers normally
    await manager.on_fill(venue.fill("fake-2", 1))
    assert len(venue.calls("place_leg")) == 3


async def test_trigger_during_exits_placing_stops_remaining_exits(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue
) -> None:
    await manager.place_bracket(TARGET, bracket_spec())
    venue.hold("place_leg")
    task = spawn(manager.on_fill(venue.fill("fake-1", 2)))  # entry done: exits start
    await spin()
    assert venue.waiting("place_leg") == 1  # the take-profit reply is delayed
    await manager.on_fill(venue.fill("fake-2", 2))  # take-profit filled: buffered
    venue.release_all("place_leg")
    await task
    assert len(venue.calls("place_leg")) == 2  # the stop-loss was never placed
    assert leg(manager, 2).status is LS.NOT_PLACED
    handle = manager.get_handle("1")
    assert isinstance(handle, BracketHandle)
    assert handle.stop_loss_client_order_id is None
    assert handle.take_profit_client_order_id == "fake-2"


async def test_unknown_exit_reply_is_resolved_by_update(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue
) -> None:
    venue.script_place("ok", "unknown", "ok")
    await manager.place_bracket(TARGET, bracket_spec())
    await manager.on_fill(venue.fill("fake-1", 2))
    await manager.on_order_update(venue.update("fake-1", OS.FILLED))
    assert record(manager).state is S.ARMED
    assert leg(manager, 1).status is LS.UNKNOWN
    await manager.on_order_update(venue.update("fake-2", OS.OPEN))
    assert leg(manager, 1).status is LS.OPEN


async def test_get_handle_is_refreshed(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue
) -> None:
    first = await manager.place_bracket(TARGET, bracket_spec())
    assert first.state is S.ENTRY_WORKING
    await manager.on_fill(venue.fill("fake-1", 2))
    await manager.on_order_update(venue.update("fake-1", OS.FILLED))
    fresh = manager.get_handle("1")
    assert first.state is S.ENTRY_WORKING  # snapshots do not change
    assert fresh.state is S.ARMED
