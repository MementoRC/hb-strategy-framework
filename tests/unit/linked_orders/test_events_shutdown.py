"""Tests L: events, the emitter, logging and shutdown."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from strategy_framework.linked_orders.config import LinkedOrderManagerConfig
from strategy_framework.linked_orders.events import LINKED_GROUP_EVENT, LinkedGroupEvent
from strategy_framework.linked_orders.events import LinkedEventKind as K
from strategy_framework.linked_orders.manager import EmulatedLinkedOrderManager
from strategy_framework.linked_orders.types import DegradedReason as R
from strategy_framework.linked_orders.types import GroupState as S
from tests.unit.linked_orders.builders import bracket_spec, oco_spec
from tests.unit.linked_orders.manager_helpers import TARGET, SpyStore, events, record

if TYPE_CHECKING:
    import pytest

    from strategy_framework.testing.fake_linked_venue import (
        FakeEmulationVenue,
        ManualClock,
        RecordingEmitter,
        StringLinkIdCodec,
    )


async def test_one_event_type_on_one_event_name(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue, emitter: RecordingEmitter
) -> None:
    await manager.place_oco(TARGET, oco_spec())
    await manager.on_fill(venue.fill("fake-1", 1))
    assert emitter.events
    assert {name for name, _ in emitter.events} == {LINKED_GROUP_EVENT}
    assert all(isinstance(p, LinkedGroupEvent) for p in emitter.payloads())
    placed = events(emitter, K.PLACED)[0]
    assert placed.group_id == "1"
    assert placed.target == TARGET
    assert placed.state is S.ARMED
    assert placed.client_order_ids == ("fake-1", "fake-2")
    assert events(emitter, K.COMPLETED)[0].residual_filled == 1


async def test_no_emitter_is_a_noop(
    venue: FakeEmulationVenue, codec: StringLinkIdCodec, clock: ManualClock
) -> None:
    manager = EmulatedLinkedOrderManager(
        venue,
        codec,
        LinkedOrderManagerConfig(enabled=True),
        store=SpyStore(venue.call_log),
        clock=clock,
    )
    handle = await manager.place_oco(TARGET, oco_spec())
    assert handle.state is S.ARMED


async def test_failing_emitter_does_not_break_the_manager(
    venue: FakeEmulationVenue,
    codec: StringLinkIdCodec,
    clock: ManualClock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    class Broken:
        def emit(self, event_type: str, payload: object) -> None:
            raise RuntimeError

    manager = EmulatedLinkedOrderManager(
        venue,
        codec,
        LinkedOrderManagerConfig(enabled=True),
        store=SpyStore(),
        clock=clock,
        bus=Broken(),
    )
    with caplog.at_level(logging.ERROR):
        handle = await manager.place_oco(TARGET, oco_spec())
    assert handle.state is S.ARMED
    assert "emitter failed" in caplog.text


async def test_degraded_is_logged_at_warning(
    manager: EmulatedLinkedOrderManager,
    venue: FakeEmulationVenue,
    caplog: pytest.LogCaptureFixture,
) -> None:
    await manager.place_oco(TARGET, oco_spec())
    with caplog.at_level(logging.WARNING):
        await manager.on_fill(venue.fill("fake-1", "0.4"))
        await manager.on_fill(venue.fill("fake-2", "0.1"))
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("double_fill" in r.getMessage() for r in warnings)


async def test_shutdown_saves_reports_and_never_cancels(
    manager: EmulatedLinkedOrderManager,
    venue: FakeEmulationVenue,
    emitter: RecordingEmitter,
    durable_store: SpyStore,
    caplog: pytest.LogCaptureFixture,
) -> None:
    await manager.place_oco(TARGET, oco_spec())
    await manager.place_bracket(TARGET, bracket_spec())
    await manager.on_fill(venue.fill("fake-3", 1))  # bracket entry partially filled
    saves_before = len(durable_store.saves)
    assert manager.has_pending_orders
    with caplog.at_level(logging.WARNING):
        await manager.shutdown()
    assert venue.calls("cancel_leg") == []
    assert len(durable_store.saves) == saves_before + 2
    opened = events(emitter, K.SHUTDOWN_OPEN)
    assert sorted(e.group_id for e in opened) == ["1", "2"]
    assert "shutdown_open" in caplog.text
    assert manager.has_pending_orders  # the legs are still live


async def test_shutdown_skips_closed_groups(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue, emitter: RecordingEmitter
) -> None:
    await manager.place_oco(TARGET, oco_spec())
    await manager.on_fill(venue.fill("fake-1", 1))
    assert not manager.has_pending_orders
    await manager.shutdown()
    assert events(emitter, K.SHUTDOWN_OPEN) == []


async def test_degraded_event_carries_both_legs_and_reason(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue, emitter: RecordingEmitter
) -> None:
    await manager.place_oco(TARGET, oco_spec())
    await manager.on_fill(venue.fill("fake-1", "0.4"))
    await manager.on_fill(venue.fill("fake-2", "0.1"))
    event = events(emitter, K.DEGRADED)[0]
    assert event.reason is R.DOUBLE_FILL
    assert event.leg_index == 1
    assert record(manager).state is S.DEGRADED
