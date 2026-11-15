"""Value types, store, events and the package surface."""

from __future__ import annotations

from decimal import Decimal

import pytest
from data_type_primitives import LegRole, LinkKind, OrderState

import strategy_framework
from strategy_framework.linked_orders import (
    LINKED_GROUP_EVENT,
    BracketHandle,
    ClockProtocol,
    GroupRecord,
    GroupState,
    InMemoryLinkedGroupStore,
    LegRecord,
    LegStatus,
    LinkedCancelOutcome,
    LinkedEventEmitter,
    LinkedEventKind,
    LinkedGroupEvent,
    LinkedGroupStore,
    OcoHandle,
)
from strategy_framework.linked_orders.types import OUTCOME_STATES, TERMINAL_STATUSES
from tests.unit.linked_orders.builders import oco_spec

D = Decimal


def _record(group_id: int = 1) -> GroupRecord:
    return GroupRecord(group_id, "BTC-USD", oco_spec(), GroupState.PLACING)


def test_leg_status_has_every_order_state_plus_not_placed() -> None:
    assert {s.name for s in OrderState} <= {s.name for s in LegStatus}
    assert LegStatus.NOT_PLACED.name not in {s.name for s in OrderState}
    for state in OrderState:
        assert LegStatus.from_order_state(state).name == state.name


def test_terminal_statuses_and_outcome_states() -> None:
    assert LegStatus.NOT_PLACED in TERMINAL_STATUSES
    assert LegStatus.OPEN not in TERMINAL_STATUSES
    assert GroupState.DEGRADED not in OUTCOME_STATES
    assert {GroupState.COMPLETED, GroupState.CANCELED, GroupState.FAILED} == OUTCOME_STATES


def test_records_are_frozen_hashable_values() -> None:
    leg = LegRecord(0, LegRole.OCO_LEG, "t", None, LegStatus.PENDING_CREATE, D(0), D(1))
    assert leg.cancel_requested is False
    assert leg.cancel_outcome is None
    rec = _record()
    assert rec.legs == ()
    assert rec.winner_leg_index is None
    assert rec.degraded_reasons == frozenset()
    assert hash(rec) == hash(_record())


def test_handles_default_to_emulated() -> None:
    assert OcoHandle("1", ("a", None), GroupState.ARMED).emulated is True
    assert BracketHandle("1", "e", None, None, GroupState.ENTRY_WORKING).emulated is True
    out = LinkedCancelOutcome("1", GroupState.CANCELED, True, D(0), (None,))
    assert out.all_legs_terminal


def test_in_memory_store_is_volatile_and_upserts() -> None:
    store = InMemoryLinkedGroupStore()
    assert store.durable is False
    store.save(_record(2))
    store.save(_record(1))
    assert [r.group_id for r in store.load_all()] == [1, 2]
    updated = GroupRecord(2, "ETH-USD", oco_spec(), GroupState.ARMED)
    store.save(updated)
    assert store.load_all()[1] == updated
    store.delete(1)
    store.delete(99)
    assert [r.group_id for r in store.load_all()] == [2]


def test_store_satisfies_protocol() -> None:
    assert isinstance(InMemoryLinkedGroupStore(), LinkedGroupStore)
    assert not isinstance(object(), LinkedGroupStore)
    assert not isinstance(object(), ClockProtocol)
    assert not isinstance(object(), LinkedEventEmitter)


def test_event_is_a_single_frozen_payload_type() -> None:
    event = LinkedGroupEvent(
        LinkedEventKind.PLACED, "1", LinkKind.OCO, "BTC-USD", GroupState.ARMED, 1.0
    )
    assert LINKED_GROUP_EVENT == "linked.group"
    assert event.deferred is False
    assert event.client_order_ids == ()
    assert event.reason is None
    with pytest.raises(AttributeError):
        event.detail = "x"  # type: ignore[misc]
    assert {k.name for k in LinkedEventKind} == {
        "PLACED",
        "LEG_UPDATED",
        "TRIGGERED",
        "COMPLETED",
        "CANCELED",
        "FAILED",
        "DEGRADED",
        "CLOSED",
        "ORPHAN_FOUND",
        "RECOVERED",
        "SHUTDOWN_OPEN",
    }


def test_linked_orders_is_opt_in() -> None:
    assert "linked_orders" not in getattr(strategy_framework, "__all__", [])
    assert "LinkedOrderManagerConfig" not in dir(strategy_framework)
