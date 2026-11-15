"""Tests H: `cancel_linked` and CANCELLING."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from data_type_primitives import OrderState

from strategy_framework.linked_orders.errors import LinkedGroupNotFoundError
from strategy_framework.linked_orders.events import LinkedEventKind as K
from strategy_framework.linked_orders.types import CancelOutcome, LegStatus, OcoHandle
from strategy_framework.linked_orders.types import DegradedReason as R
from strategy_framework.linked_orders.types import GroupState as S
from tests.unit.linked_orders.builders import bracket_spec, oco_spec
from tests.unit.linked_orders.manager_helpers import TARGET, events, record, spawn, spin

if TYPE_CHECKING:
    from strategy_framework.linked_orders.manager import EmulatedLinkedOrderManager
    from strategy_framework.testing.fake_linked_venue import (
        FakeEmulationVenue,
        RecordingEmitter,
    )

D = Decimal
OS = OrderState


async def test_cancel_armed_group(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue, emitter: RecordingEmitter
) -> None:
    handle = await manager.place_oco(TARGET, oco_spec())
    outcome = await manager.cancel_linked(handle)
    assert outcome.state is S.CANCELED
    assert outcome.all_legs_terminal is True
    assert outcome.residual_filled == 0
    assert outcome.leg_outcomes == (CancelOutcome.CANCELED, CancelOutcome.CANCELED)
    assert K.CANCELED in emitter.kinds()
    again = await manager.cancel_linked(handle)  # idempotent on an outcome state
    assert again.state is S.CANCELED
    assert len(venue.calls("cancel_leg")) == 2


async def test_unknown_leg_is_cancelled_when_it_resolves(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue
) -> None:
    venue.script_place("ok", "unknown")
    handle = await manager.place_oco(TARGET, oco_spec())
    outcome = await manager.cancel_linked(handle)
    assert outcome.state is S.CANCELLING
    assert outcome.all_legs_terminal is False
    assert [c[2] for c in venue.calls("cancel_leg")] == ["fake-1"]
    await manager.on_order_update(venue.update("fake-2", OS.OPEN))
    assert [c[2] for c in venue.calls("cancel_leg")] == ["fake-1", "fake-2"]
    assert manager.get_handle("1").state is S.CANCELED


async def test_fill_while_cancelling_sets_winner_second_fill_is_double_fill(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue
) -> None:
    handle = await manager.place_oco(TARGET, oco_spec())
    venue.hold("cancel_leg")
    task = spawn(manager.cancel_linked(handle))
    await spin()
    assert record(manager).state is S.CANCELLING
    await manager.on_fill(venue.fill("fake-1", "0.5"))
    assert record(manager).winner_leg_index == 0
    assert record(manager).state is S.CANCELLING
    await manager.on_fill(venue.fill("fake-2", "0.5"))
    assert record(manager).degraded_reasons == {R.DOUBLE_FILL}
    venue.release_all("cancel_leg")
    await task


async def test_cancel_during_entry_working_never_places_exits(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue
) -> None:
    handle = await manager.place_bracket(TARGET, bracket_spec())
    await manager.on_fill(venue.fill("fake-1", 1))
    outcome = await manager.cancel_linked(handle)
    assert outcome.state is S.CANCELED
    assert outcome.residual_filled == D(1)
    assert len(venue.calls("place_leg")) == 1
    assert [leg.status for leg in record(manager).legs[1:]] == [LegStatus.NOT_PLACED] * 2


async def test_cancel_unknown_handle_raises(manager: EmulatedLinkedOrderManager) -> None:
    with pytest.raises(LinkedGroupNotFoundError):
        await manager.cancel_linked(OcoHandle("77", (), S.ARMED))


async def test_cancel_while_leg_reply_pending_cancels_on_reply(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue
) -> None:
    venue.hold("place_leg")
    task = spawn(manager.place_oco(TARGET, oco_spec(3)))
    await spin()
    venue.release("place_leg")
    await spin()
    handle = manager.get_handle("1")
    outcome = await manager.cancel_linked(handle)  # leg 1's reply is pending
    assert outcome.state is S.CANCELLING
    venue.release_all("place_leg")
    placed = await task
    assert placed.state is S.CANCELED
    assert len(venue.calls("place_leg")) == 2  # leg 2 never placed
    assert sorted(c[2] for c in venue.calls("cancel_leg")) == ["fake-1", "fake-2"]


async def test_external_cancel_keeps_armed_until_one_leg_remains(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue, emitter: RecordingEmitter
) -> None:
    await manager.place_oco(TARGET, oco_spec(3))
    await manager.on_order_update(venue.update("fake-1", OS.CANCELED))
    assert record(manager).state is S.ARMED
    assert K.LEG_UPDATED in emitter.kinds()
    await manager.on_order_update(venue.update("fake-2", OS.CANCELED))
    assert record(manager).state is S.DEGRADED
    assert [e.reason for e in events(emitter, K.DEGRADED)] == [R.LINK_BROKEN]
