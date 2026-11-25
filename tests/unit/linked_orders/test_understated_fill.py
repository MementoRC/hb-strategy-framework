"""A terminal FILLED snapshot below the placed amount stays unresolved (issue #105)."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from data_type_primitives import OrderState

from strategy_framework.linked_orders.types import DegradedReason, GroupState, LegStatus
from tests.unit.linked_orders.builders import Sim, bracket_spec
from tests.unit.linked_orders.manager_helpers import TARGET, leg, record
from tests.unit.linked_orders.test_recovery import restart

if TYPE_CHECKING:
    from strategy_framework.linked_orders.manager import EmulatedLinkedOrderManager
    from strategy_framework.testing.fake_linked_venue import (
        FakeEmulationVenue,
        ManualClock,
        StringLinkIdCodec,
    )
    from tests.unit.linked_orders.manager_helpers import SpyStore

D = Decimal


def test_understated_filled_snapshot_stays_unresolved_and_places_nothing() -> None:
    sim = Sim(bracket_spec()).place(0).snap(0, OrderState.FILLED, 1)
    assert sim.rec.state is GroupState.ENTRY_WORKING
    assert sim.leg(0).unresolved_since is not None
    assert len(sim.rec.legs) == 1
    assert sim.cancels == []
    sim.tick(1.0)
    assert sim.get_legs == [0]
    assert sim.rec.state is GroupState.ENTRY_WORKING
    assert len(sim.rec.legs) == 1


def test_corrected_snapshot_resolves_and_sizes_exits_on_full_amount() -> None:
    sim = Sim(bracket_spec()).place(0).snap(0, OrderState.FILLED, 1)
    sim.snap(0, OrderState.FILLED, 2)
    assert sim.leg(0).unresolved_since is None
    assert sim.rec.state is GroupState.EXITS_PLACING
    sim.begin(1)
    assert sim.leg(1).placed_amount == D(2)


def test_full_fill_resolves_immediately_and_canceled_zero_fill_unchanged() -> None:
    sim = Sim(bracket_spec()).place(0).snap(0, OrderState.FILLED, 2)
    assert sim.leg(0).unresolved_since is None
    assert sim.rec.state is GroupState.EXITS_PLACING
    canceled = Sim(bracket_spec()).place(0).snap(0, OrderState.CANCELED, 0)
    assert canceled.rec.state is GroupState.CANCELED


def test_persistently_understated_fill_degrades_past_grace() -> None:
    sim = Sim(bracket_spec()).place(0).snap(0, OrderState.FILLED, 1)
    sim.tick(31)
    assert sim.rec.state is GroupState.DEGRADED
    assert DegradedReason.UNRESOLVED_PAST_GRACE in sim.rec.degraded_reasons


async def test_recover_holds_understated_filled_leg_unresolved(
    manager: EmulatedLinkedOrderManager,
    venue: FakeEmulationVenue,
    codec: StringLinkIdCodec,
    clock: ManualClock,
    durable_store: SpyStore,
) -> None:
    await manager.place_bracket(TARGET, bracket_spec())
    venue.fill("fake-1", 1)
    venue.update("fake-1", OrderState.FILLED)  # terminal, but filled 1 < placed 2
    fresh = restart(venue, codec, clock, durable_store)
    await fresh.recover([TARGET])
    assert leg(fresh, 0).status is LegStatus.FILLED
    assert leg(fresh, 0).unresolved_since is not None
    assert record(fresh).state is GroupState.ENTRY_WORKING
    assert len(venue.calls("place_leg")) == 1
