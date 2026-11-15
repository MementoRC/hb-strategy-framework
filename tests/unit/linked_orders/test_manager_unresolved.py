"""Tests C (unresolved legs), E (double fill) and F (rollback)."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING

from data_type_primitives import OrderState

from strategy_framework.linked_orders.events import LinkedEventKind as K
from strategy_framework.linked_orders.types import CancelOutcome, LegFill, LegStatus
from strategy_framework.linked_orders.types import DegradedReason as R
from strategy_framework.linked_orders.types import GroupState as S
from tests.unit.linked_orders.builders import oco_spec
from tests.unit.linked_orders.manager_helpers import (
    TARGET,
    SpyStore,
    events,
    leg,
    record,
    spawn,
    spin,
)

if TYPE_CHECKING:
    import pytest

    from strategy_framework.linked_orders.manager import EmulatedLinkedOrderManager
    from strategy_framework.testing.fake_linked_venue import (
        FakeEmulationVenue,
        ManualClock,
        RecordingEmitter,
    )

D = Decimal
OS = OrderState
LS = LegStatus


def cancels(venue: FakeEmulationVenue) -> list[str]:
    return [c[2] for c in venue.calls("cancel_leg")]


# ------------------------------------------------------------------ C. unresolved


async def test_unknown_leg_defers_cancel_then_resolves_open(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue, emitter: RecordingEmitter
) -> None:
    venue.script_place("ok", "unknown")
    handle = await manager.place_oco(TARGET, oco_spec())
    assert handle.state is S.ARMED
    await manager.on_fill(venue.fill("fake-1", 1))
    assert cancels(venue) == []
    assert events(emitter, K.TRIGGERED)[0].deferred is True
    await manager.on_order_update(venue.update("fake-2", OS.OPEN))
    assert cancels(venue) == ["fake-2"]
    assert manager.get_handle("1").state is S.COMPLETED


async def test_unknown_leg_resolving_failed_completes_without_cancel(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue
) -> None:
    venue.script_place("ok", "unknown")
    await manager.place_oco(TARGET, oco_spec())
    await manager.on_fill(venue.fill("fake-1", 1))
    await manager.on_order_update(venue.update("fake-2", OS.FAILED))
    assert cancels(venue) == []
    assert manager.get_handle("1").state is S.COMPLETED


async def test_unknown_leg_resolving_filled_is_double_fill(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue, emitter: RecordingEmitter
) -> None:
    venue.script_place("ok", "unknown")
    await manager.place_oco(TARGET, oco_spec())
    await manager.on_fill(venue.fill("fake-1", 1))
    await manager.on_fill(venue.fill("fake-2", 1))
    assert manager.get_handle("1").state is S.DEGRADED
    assert record(manager).degraded_reasons == {R.DOUBLE_FILL}
    assert events(emitter, K.TRIGGERED)[0].deferred is True
    assert len(venue.calls("place_leg")) == 2  # no compensating order
    assert cancels(venue) == []


async def test_pending_create_leg_defers_cancel_until_reply(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue, emitter: RecordingEmitter
) -> None:
    venue.hold("place_leg")
    task = spawn(manager.place_oco(TARGET, oco_spec()))
    await spin()
    venue.release("place_leg")
    await spin()
    await manager.on_fill(venue.fill("fake-1", 1))  # leg 1's reply is still pending
    assert cancels(venue) == []
    assert events(emitter, K.TRIGGERED)[0].deferred is True
    venue.release_all("place_leg")
    handle = await task
    assert cancels(venue) == ["fake-2"]
    assert handle.state is S.COMPLETED


async def test_past_grace_degrades_once(
    manager: EmulatedLinkedOrderManager,
    venue: FakeEmulationVenue,
    clock: ManualClock,
    emitter: RecordingEmitter,
    caplog: pytest.LogCaptureFixture,
) -> None:
    venue.script_place("ok", "unknown")
    await manager.place_oco(TARGET, oco_spec())
    venue.script_get(None, None, None)
    await manager.tick()
    assert record(manager).state is S.ARMED
    clock.advance(31)
    with caplog.at_level(logging.WARNING):
        await manager.tick()
        await manager.tick()
    degraded = events(emitter, K.DEGRADED)
    assert [e.reason for e in degraded] == [R.UNRESOLVED_PAST_GRACE]
    assert "unresolved_past_grace" in caplog.text or "degraded" in caplog.text


async def test_not_found_cancel_stays_unresolved_until_get_leg_answers(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue
) -> None:
    await manager.place_oco(TARGET, oco_spec())
    venue.script_cancel(CancelOutcome.NOT_FOUND)
    await manager.on_fill(venue.fill("fake-1", 1))
    assert record(manager).state is S.TRIGGERED
    assert leg(manager, 1).cancel_outcome is CancelOutcome.NOT_FOUND
    venue.script_get(None)  # get_leg has no answer: still unresolved
    await manager.tick()
    assert record(manager).state is S.TRIGGERED
    await manager.tick()  # get_leg answers OPEN: the cancel is re-sent
    assert cancels(venue) == ["fake-2", "fake-2"]
    assert manager.get_handle("1").state is S.COMPLETED


async def test_queued_cancel_that_went_stale_is_withdrawn_and_redone(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue
) -> None:
    await manager.place_oco(TARGET, oco_spec(3))
    venue.hold("cancel_leg")
    task = spawn(manager.on_fill(venue.fill("fake-1", 1)))  # cancels fake-2 then fake-3
    await spin()
    assert cancels(venue) == ["fake-2"]
    await manager.on_order_update(venue.update("fake-3", OS.UNKNOWN))  # venue lost track of it
    venue.release_all("cancel_leg")
    await task
    assert cancels(venue) == ["fake-2"]  # the queued cancel of fake-3 was NOT sent
    assert leg(manager, 2).cancel_requested is False
    await manager.on_order_update(venue.update("fake-3", OS.OPEN))  # resolves: cancelled now
    assert cancels(venue) == ["fake-2", "fake-3"]
    assert manager.get_handle("1").state is S.COMPLETED


async def test_cancel_and_get_failures_leave_the_leg_unresolved(
    venue: FakeEmulationVenue, manager: EmulatedLinkedOrderManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    await manager.place_oco(TARGET, oco_spec())

    async def boom(*_a: object, **_k: object) -> object:
        raise RuntimeError

    monkeypatch.setattr(venue, "cancel_leg", boom)
    monkeypatch.setattr(venue, "get_leg", boom)
    await manager.on_fill(venue.fill("fake-1", 1))
    assert leg(manager, 1).cancel_outcome is CancelOutcome.UNKNOWN
    await manager.tick()
    assert record(manager).state is S.TRIGGERED


# ------------------------------------------------------------------ E. double fill


async def test_already_filled_cancel_outcome_is_double_fill(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue, emitter: RecordingEmitter
) -> None:
    await manager.place_oco(TARGET, oco_spec())
    venue.script_cancel(CancelOutcome.ALREADY_FILLED)
    await manager.on_fill(venue.fill("fake-1", 1))
    assert manager.get_handle("1").state is S.DEGRADED
    event = events(emitter, K.DEGRADED)[0]
    assert event.reason is R.DOUBLE_FILL
    assert event.client_order_ids == ("fake-1", "fake-2")
    assert event.filled == (D(1), D(1))
    assert len(venue.calls("place_leg")) == 2


async def test_sibling_fill_after_cancel_requested(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue
) -> None:
    await manager.place_oco(TARGET, oco_spec())
    venue.hold("cancel_leg")
    task = spawn(manager.on_fill(venue.fill("fake-1", 1)))
    await spin()
    assert venue.waiting("cancel_leg") == 1
    await manager.on_fill(venue.fill("fake-2", "0.5"))
    assert record(manager).degraded_reasons == {R.DOUBLE_FILL}
    venue.release_all("cancel_leg")
    await task
    assert len(venue.calls("place_leg")) == 2


async def test_canceled_with_fill_sibling_and_tombstone_reopen(
    manager: EmulatedLinkedOrderManager,
    venue: FakeEmulationVenue,
    durable_store: SpyStore,
    emitter: RecordingEmitter,
) -> None:
    await manager.place_oco(TARGET, oco_spec())
    await manager.on_fill(venue.fill("fake-1", 1))
    assert durable_store.load_all() == []  # closed: a tombstone
    assert not manager.has_pending_orders
    await manager.on_fill(venue.fill("fake-2", "0.3"))  # late CANCELED-with-fill report
    stored = durable_store.load_all()
    assert len(stored) == 1
    assert stored[0].state is S.DEGRADED
    assert manager.has_pending_orders
    assert [e.reason for e in events(emitter, K.DEGRADED)] == [R.DOUBLE_FILL]
    await manager.tick()  # every leg is terminal: closes again
    assert durable_store.load_all() == []
    assert len(venue.calls("place_leg")) == 2


async def test_sibling_fill_after_completed_with_winner_working(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue
) -> None:
    await manager.place_oco(TARGET, oco_spec())
    await manager.on_fill(venue.fill("fake-1", "0.4"))
    assert manager.get_handle("1").state is S.COMPLETED
    await manager.on_fill(venue.fill("fake-2", "0.1"))
    assert manager.get_handle("1").state is S.DEGRADED
    assert len(venue.calls("place_leg")) == 2


async def test_late_events_after_tombstone_ttl_are_unmatched(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue, clock: ManualClock
) -> None:
    await manager.place_oco(TARGET, oco_spec())
    await manager.on_fill(venue.fill("fake-1", 1))
    clock.advance(301)
    await manager.tick()
    await manager.on_fill(LegFill("fake-2", D(1), D(1), 0.0))
    assert 1 not in manager._groups  # noqa: SLF001
    assert len(manager._buffer) == 1  # noqa: SLF001


# ------------------------------------------------------------------ F. rollback


async def test_second_leg_rejected_rolls_back_first(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue, emitter: RecordingEmitter
) -> None:
    venue.script_place("ok", "reject")
    handle = await manager.place_oco(TARGET, oco_spec())
    assert handle.state is S.FAILED
    assert handle.leg_client_order_ids == ("fake-1", None)
    assert cancels(venue) == ["fake-1"]
    assert len(venue.calls("place_leg")) == 2  # never retried
    assert K.FAILED in emitter.kinds()


async def test_rejection_while_a_leg_is_unknown_defers_rollback(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue
) -> None:
    venue.script_place("unknown", "ok", "reject")
    handle = await manager.place_oco(TARGET, oco_spec(3))
    assert handle.state is S.CANCELLING
    assert cancels(venue) == []
    await manager.on_order_update(venue.update("fake-1", OS.OPEN))
    assert sorted(cancels(venue)) == ["fake-1", "fake-2"]
    assert manager.get_handle("1").state is S.FAILED


async def test_rollback_still_runs_when_degraded_by_grace(
    manager: EmulatedLinkedOrderManager,
    venue: FakeEmulationVenue,
    clock: ManualClock,
    durable_store: SpyStore,
) -> None:
    venue.script_place("unknown", "ok", "reject")
    await manager.place_oco(TARGET, oco_spec(3))
    clock.advance(31)
    venue.script_get(None)
    await manager.tick()
    assert record(manager).state is S.DEGRADED
    assert cancels(venue) == []
    await manager.on_order_update(venue.update("fake-1", OS.OPEN))
    assert sorted(cancels(venue)) == ["fake-1", "fake-2"]
    assert durable_store.load_all() == []  # every leg terminal: closed (still DEGRADED)
    assert manager.get_handle("1").state is S.DEGRADED
    assert len(venue.calls("place_leg")) == 3


async def test_fill_during_rollback_is_winner_second_fill_is_double_fill(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue
) -> None:
    venue.script_place("ok", "ok", "reject")
    venue.hold("cancel_leg")
    task = spawn(manager.place_oco(TARGET, oco_spec(3)))
    await spin()
    assert record(manager).state is S.CANCELLING
    await manager.on_fill(venue.fill("fake-2", "0.5"))
    assert record(manager).winner_leg_index == 1
    assert record(manager).state is S.CANCELLING
    await manager.on_fill(venue.fill("fake-1", "0.2"))
    assert record(manager).degraded_reasons == {R.DOUBLE_FILL}
    venue.release_all("cancel_leg")
    await task
    assert len(venue.calls("place_leg")) == 3
