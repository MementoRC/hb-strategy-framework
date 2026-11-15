"""Tests B (OCO), D (intake ordering) and the OCO-specific parts of C."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING

from data_type_primitives import OrderState, OrderUpdate

from strategy_framework.linked_orders.config import LinkedOrderManagerConfig
from strategy_framework.linked_orders.events import LinkedEventKind as K
from strategy_framework.linked_orders.manager import EmulatedLinkedOrderManager
from strategy_framework.linked_orders.types import GroupState as S
from strategy_framework.linked_orders.types import LegFill, LegStatus
from tests.unit.linked_orders.builders import oco_spec
from tests.unit.linked_orders.manager_helpers import (
    TARGET,
    SpyStore,
    assert_write_ahead,
    leg,
    record,
    spawn,
    spin,
)

if TYPE_CHECKING:
    import pytest

    from strategy_framework.testing.fake_linked_venue import (
        FakeEmulationVenue,
        ManualClock,
        RecordingEmitter,
        StringLinkIdCodec,
    )

D = Decimal
OS = OrderState
LS = LegStatus


# ------------------------------------------------------------------ B. OCO basics


async def test_legs_are_placed_in_order_with_tags_and_write_ahead(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue
) -> None:
    handle = await manager.place_oco(TARGET, oco_spec())
    assert handle.state is S.ARMED
    assert handle.emulated is True
    assert handle.leg_client_order_ids == ("fake-1", "fake-2")
    assert [c[3] for c in venue.calls("place_leg")] == ["hbl-1-0", "hbl-1-1"]
    assert_write_ahead(venue.call_log)
    assert manager.get_handle("1") == handle
    assert manager.has_pending_orders


async def test_full_fill_triggers_cancels_sibling_and_closes(
    manager: EmulatedLinkedOrderManager,
    venue: FakeEmulationVenue,
    emitter: RecordingEmitter,
    durable_store: SpyStore,
) -> None:
    await manager.place_oco(TARGET, oco_spec())
    await manager.on_fill(venue.fill("fake-1", 1))
    assert [c[2] for c in venue.calls("cancel_leg")] == ["fake-2"]
    assert manager.get_handle("1").state is S.COMPLETED
    assert durable_store.load_all() == []
    assert durable_store.deletes == [1]
    kinds = emitter.kinds()
    assert K.TRIGGERED in kinds
    assert K.COMPLETED in kinds
    assert kinds[-1] is K.CLOSED
    assert not manager.has_pending_orders


async def test_partial_fill_triggers_and_close_waits_for_winner(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue, durable_store: SpyStore
) -> None:
    await manager.place_oco(TARGET, oco_spec())
    await manager.on_fill(venue.fill("fake-2", "0.4"))
    assert manager.get_handle("1").state is S.COMPLETED
    assert durable_store.deletes == []  # winner still working
    assert manager.has_pending_orders
    # later fills on the winner do not re-trigger
    await manager.on_fill(venue.fill("fake-2", "0.7"))
    assert len(venue.calls("cancel_leg")) == 1
    await manager.on_fill(venue.fill("fake-2", 1))
    assert durable_store.deletes == [1]
    assert not manager.has_pending_orders


# ------------------------------------------------------------------ D. intake ordering


async def test_fill_for_pending_leg_is_buffered_and_replayed_before_any_cancel(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue
) -> None:
    venue.hold("place_leg")
    task = spawn(manager.place_oco(TARGET, oco_spec(3)))
    await spin()
    venue.release("place_leg")  # leg 0 acknowledged
    await spin()
    assert venue.waiting("place_leg") == 1  # leg 1's reply is delayed
    await manager.on_fill(venue.fill("fake-2", 1))  # not registered yet: buffered
    assert leg(manager, 1).filled == 0
    venue.release_all("place_leg")
    handle = await task
    assert [c[2] for c in venue.calls("cancel_leg")] == ["fake-1"]  # leg 2 never placed
    assert record(manager).winner_leg_index == 1
    assert handle.leg_client_order_ids == ("fake-1", "fake-2", None)
    assert len(venue.calls("place_leg")) == 2
    assert handle.state is S.COMPLETED


async def test_trigger_during_placing_seals_remaining_legs(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue
) -> None:
    venue.hold("place_leg")
    task = spawn(manager.place_oco(TARGET, oco_spec(3)))
    await spin()
    await manager.on_fill(venue.fill("fake-1", 1))  # leg 0 reply still pending
    venue.release_all("place_leg")
    handle = await task
    assert len(venue.calls("place_leg")) == 1
    assert [leg(manager, i).status for i in range(3)] == [
        LS.FILLED,
        LS.NOT_PLACED,
        LS.NOT_PLACED,
    ]
    assert handle.leg_client_order_ids == ("fake-1", None, None)


async def test_buffer_overflow_evicts_oldest_with_warning(
    venue: FakeEmulationVenue,
    codec: StringLinkIdCodec,
    clock: ManualClock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    config = LinkedOrderManagerConfig(enabled=True, unmatched_buffer_max=2)
    manager = EmulatedLinkedOrderManager(venue, codec, config, store=SpyStore(), clock=clock)
    with caplog.at_level(logging.WARNING):
        for cid in ("a", "b", "c"):
            await manager.on_fill(LegFill(cid, D(1), D(1), 0.0))
    assert "dropped report for a" in caplog.text
    assert len(manager._buffer) == 2  # noqa: SLF001


async def test_buffer_ttl_expiry_warns(
    manager: EmulatedLinkedOrderManager, clock: ManualClock, caplog: pytest.LogCaptureFixture
) -> None:
    await manager.on_fill(LegFill("ghost", D(1), D(1), 0.0))
    await manager.tick()
    assert len(manager._buffer) == 1  # noqa: SLF001
    clock.advance(31)
    with caplog.at_level(logging.WARNING):
        await manager.tick()
    assert "unmatched report for ghost expired" in caplog.text
    assert len(manager._buffer) == 0  # noqa: SLF001


async def test_update_without_client_order_id_is_ignored(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue
) -> None:
    await manager.on_order_update(OrderUpdate(TARGET, 0.0, OS.FILLED, None))
    assert len(manager._buffer) == 0  # noqa: SLF001


async def test_duplicate_fill_id_and_lower_cumulative_are_dropped(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue
) -> None:
    await manager.place_oco(TARGET, oco_spec())
    await manager.on_fill(venue.fill("fake-1", "0.2", fill_id="x"))
    await manager.on_fill(venue.fill("fake-1", "0.5", fill_id="x"))  # duplicate id
    assert leg(manager, 0).filled == D("0.2")
    await manager.on_fill(LegFill("fake-1", D("0.1"), D(100), 0.0))  # lower cumulative
    assert leg(manager, 0).filled == D("0.2")
    await manager.on_fill(LegFill("fake-1", D("0.3"), D(100), 0.0, "y"))
    assert leg(manager, 0).filled == D("0.3")


async def test_stale_open_after_partial_and_terminal_never_regress(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue
) -> None:
    await manager.place_oco(TARGET, oco_spec())
    await manager.on_fill(venue.fill("fake-1", "0.4"))
    await manager.on_order_update(venue.update("fake-1", OS.OPEN))
    assert leg(manager, 0).status is LS.PARTIALLY_FILLED
    await manager.on_fill(venue.fill("fake-1", 1))
    await manager.on_order_update(venue.update("fake-1", OS.OPEN))
    assert leg(manager, 0).status is LS.FILLED


async def test_buffered_duplicates_are_filtered_on_replay(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue
) -> None:
    venue.hold("place_leg")
    task = spawn(manager.place_oco(TARGET, oco_spec()))
    await spin()
    fill = venue.fill("fake-1", "0.5", fill_id="f1")
    await manager.on_fill(fill)
    await manager.on_fill(fill)  # duplicate fill_id
    await manager.on_order_update(venue.update("fake-1", OS.PARTIALLY_FILLED))
    venue.release_all("place_leg")
    await task
    assert leg(manager, 0).filled == D("0.5")
    assert record(manager).winner_leg_index == 0
