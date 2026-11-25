"""A terminal FILLED snapshot below the placed amount stays unresolved (issue #105)."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from data_type_primitives import OrderState

from strategy_framework.linked_orders.config import (
    DEFAULT_UNDERSTATED_FILL_CONFIRMATIONS,
    LinkedOrderManagerConfig,
)
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


def test_changing_understated_fill_degrades_past_grace() -> None:
    sim = Sim(bracket_spec()).place(0)
    for value in ("1", "1.1", "1.2", "1.3"):
        sim.snap(0, OrderState.FILLED, value)
    sim.tick(31)
    assert sim.rec.state is GroupState.DEGRADED
    assert DegradedReason.UNRESOLVED_PAST_GRACE in sim.rec.degraded_reasons


def test_zero_fill_filled_is_never_accepted_however_often_repeated() -> None:
    sim = Sim(bracket_spec()).place(0)
    for _ in range(10):
        sim.snap(0, OrderState.FILLED, 0)
    assert sim.leg(0).unresolved_since is not None
    assert len(sim.rec.legs) == 1
    sim.tick(31)
    assert DegradedReason.UNRESOLVED_PAST_GRACE in sim.rec.degraded_reasons


def test_fewer_than_n_identical_reports_stay_unresolved() -> None:
    sim = Sim(bracket_spec()).place(0)
    for _ in range(DEFAULT_UNDERSTATED_FILL_CONFIRMATIONS - 1):
        sim.snap(0, OrderState.FILLED, 1)
    assert sim.leg(0).unresolved_since is not None
    assert sim.rec.state is GroupState.ENTRY_WORKING
    assert len(sim.rec.legs) == 1


def test_n_identical_reports_accept_and_size_exits_on_reported_fill() -> None:
    sim = Sim(bracket_spec()).place(0)
    for _ in range(DEFAULT_UNDERSTATED_FILL_CONFIRMATIONS):
        sim.snap(0, OrderState.FILLED, 1)
    assert sim.leg(0).unresolved_since is None
    assert sim.rec.state is GroupState.EXITS_PLACING
    sim.tick(31)
    assert DegradedReason.UNRESOLVED_PAST_GRACE not in sim.rec.degraded_reasons
    sim.begin(1)
    assert sim.leg(1).placed_amount == D(1)


def test_order_updates_never_count_only_snapshots_do() -> None:
    sim = Sim(bracket_spec()).place(0).snap(0, OrderState.FILLED, 1)
    for _ in range(5):
        sim.update(0, OrderState.FILLED)
    assert sim.leg(0).fill_reports == 1
    assert sim.leg(0).unresolved_since is not None
    sim.snap(0, OrderState.FILLED, 1)
    assert sim.leg(0).unresolved_since is not None
    sim.snap(0, OrderState.FILLED, 1)
    assert sim.leg(0).unresolved_since is None


def test_order_update_with_other_status_resets_the_count() -> None:
    sim = Sim(bracket_spec()).place(0)
    sim.snap(0, OrderState.FILLED, 1).snap(0, OrderState.FILLED, 1)
    sim.update(0, OrderState.OPEN)
    assert sim.leg(0).fill_reports == 0
    assert sim.leg(0).status is LegStatus.FILLED
    sim.snap(0, OrderState.FILLED, 1).snap(0, OrderState.FILLED, 1)
    assert sim.leg(0).unresolved_since is not None
    sim.snap(0, OrderState.FILLED, 1)
    assert sim.leg(0).unresolved_since is None


def test_fill_events_below_placed_never_increment_the_count() -> None:
    sim = Sim(bracket_spec()).place(0).snap(0, OrderState.FILLED, 1)
    assert sim.leg(0).fill_reports == 1
    for _ in range(5):
        sim.fill(0, 1)
    assert sim.leg(0).fill_reports == 1
    assert sim.leg(0).unresolved_since is not None
    fills = Sim(bracket_spec()).place(0).fill(0, 1)
    for _ in range(5):
        fills.fill(0, 1)
    assert fills.leg(0).status is LegStatus.PARTIALLY_FILLED
    assert fills.leg(0).fill_reports == 0


def test_larger_fill_event_between_snapshots_restarts_the_count() -> None:
    sim = Sim(bracket_spec()).place(0)
    sim.snap(0, OrderState.FILLED, 1).snap(0, OrderState.FILLED, 1)
    sim.fill(0, "1.5")
    assert sim.leg(0).fill_reports == 0
    for _ in range(DEFAULT_UNDERSTATED_FILL_CONFIRMATIONS - 1):
        sim.snap(0, OrderState.FILLED, "1.5")
        assert sim.leg(0).unresolved_since is not None
    sim.snap(0, OrderState.FILLED, "1.5")
    assert sim.leg(0).unresolved_since is None
    assert sim.leg(0).filled == D("1.5")


def test_stale_lower_snapshot_resets_count_and_does_not_move_status() -> None:
    sim = Sim(bracket_spec()).place(0).fill(0, "1.5")
    sim.snap(0, OrderState.FILLED, 1)
    assert sim.leg(0).status is LegStatus.PARTIALLY_FILLED
    assert sim.leg(0).filled == D("1.5")
    assert sim.leg(0).fill_reports == 0
    sim.snap(0, OrderState.FILLED, "1.5").snap(0, OrderState.FILLED, "1.5")
    sim.snap(0, OrderState.FILLED, 1)
    assert sim.leg(0).fill_reports == 0
    assert sim.leg(0).unresolved_since is not None


def test_changed_value_restarts_the_count() -> None:
    sim = Sim(bracket_spec()).place(0)
    sim.snap(0, OrderState.FILLED, 1).snap(0, OrderState.FILLED, 1)
    sim.snap(0, OrderState.FILLED, "1.5")
    assert sim.leg(0).unresolved_since is not None
    sim.snap(0, OrderState.FILLED, "1.5").snap(0, OrderState.FILLED, "1.5")
    assert sim.leg(0).unresolved_since is None
    sim.begin(1)
    assert sim.leg(1).placed_amount == D("1.5")


def test_accepted_leg_does_not_regress_on_duplicate_or_lower_fill_events() -> None:
    sim = Sim(bracket_spec()).place(0)
    for _ in range(DEFAULT_UNDERSTATED_FILL_CONFIRMATIONS):
        sim.snap(0, OrderState.FILLED, 1)
    for cumulative in ("1", "0.5"):
        sim.fill(0, cumulative)
        assert sim.leg(0).status is LegStatus.FILLED
        assert sim.leg(0).unresolved_since is None
        assert sim.rec.state is GroupState.EXITS_PLACING


def test_lower_fill_after_acceptance_leaves_filled_and_status_unchanged() -> None:
    sim = Sim(bracket_spec()).place(0)
    for _ in range(DEFAULT_UNDERSTATED_FILL_CONFIRMATIONS):
        sim.snap(0, OrderState.FILLED, 1)
    before = sim.leg(0)
    sim.fill(0, "0.5")
    after = sim.leg(0)
    assert after.filled == D(1)
    assert after.status is LegStatus.FILLED
    assert after.fill_reports == before.fill_reports
    assert after.unresolved_since is None
    sim.snap(0, OrderState.FILLED, "0.5")
    assert sim.leg(0).filled == D(1)
    assert sim.leg(0).status is LegStatus.FILLED
    assert sim.leg(0).unresolved_since is None


def test_confirmations_config_rejects_zero() -> None:
    assert LinkedOrderManagerConfig().understated_fill_confirmations == 3
    with pytest.raises(ValueError, match="understated_fill_confirmations"):
        LinkedOrderManagerConfig(understated_fill_confirmations=0)


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
