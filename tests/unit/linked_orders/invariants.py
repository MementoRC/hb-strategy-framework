"""I1-I8 checker for pure state-machine transitions (reusable by the interleaving test)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from strategy_framework.linked_orders.events import LinkedEventKind
from strategy_framework.linked_orders.state import (
    CancelLeg,
    Delete,
    Emit,
    Persist,
    PlaceLeg,
    any_unresolved,
    can_place,
    durable,
    is_terminal,
    is_unresolved,
    leg_count,
    link_indices,
)
from strategy_framework.linked_orders.types import (
    OUTCOME_STATES,
    DegradedReason,
    GroupRecord,
    GroupState,
    LegStatus,
)

if TYPE_CHECKING:
    from strategy_framework.linked_orders.state import Transition

_NEVER_PLACE = {GroupState.TRIGGERED, GroupState.CANCELLING, *OUTCOME_STATES}
_REGRESSIVE = {
    LegStatus.PENDING_CREATE,
    LegStatus.OPEN,
    LegStatus.CREATED,
    LegStatus.APPROVED,
    LegStatus.PENDING_APPROVAL,
}


def violations(prev: GroupRecord | None, trans: Transition, *, closed: bool = False) -> list[str]:
    new, acts = trans.record, trans.actions
    out: list[str] = []
    out += _i1(new, acts)
    out += _i2(prev, new, acts)
    out += _i3(prev, new, acts)
    out += _i4_i7(prev, new, acts, closed)
    out += _i5(new)
    out += _i6_i8(prev, new)
    return out


def monotonic_violations(prev: GroupRecord, new: GroupRecord) -> list[str]:
    """I6 + I8 between two successive records of one group."""
    return _i6_i8(prev, new)


def sibling_fill_violations(new: GroupRecord) -> list[str]:
    """I5 for one record."""
    return _i5(new)


def _i1(new: GroupRecord, acts: tuple[object, ...]) -> list[str]:
    out = []
    for act in acts:
        if not isinstance(act, CancelLeg):
            continue
        if is_unresolved(new.legs[act.leg_index]):
            out.append(f"I1: cancel of unresolved leg {act.leg_index}")
        if new.cancel_cause != "user" and any_unresolved(new):
            out.append("I1: fill-triggered/rollback cancel while a leg is unresolved")
    return out


def _i2(prev: GroupRecord | None, new: GroupRecord, acts: tuple[object, ...]) -> list[str]:
    out = []
    entered = new.state in OUTCOME_STATES and (prev is None or prev.state not in OUTCOME_STATES)
    if entered:
        if any_unresolved(new):
            out.append("I2: outcome state with an unresolved leg")
        live = [leg.leg_index for leg in new.legs if not is_terminal(leg)]
        allowed = [new.winner_leg_index] if new.state is GroupState.COMPLETED else []
        if any(i not in allowed for i in live):
            out.append(f"I2: outcome {new.state.name} with live legs {live}")
    if any(isinstance(a, Delete) for a in acts) and (
        len(new.legs) != leg_count(new)
        or not all(is_terminal(leg) for leg in new.legs)
        or any_unresolved(new)
    ):
        out.append("I2: store.delete before every leg is terminal and resolved")
    return out


def _i3(prev: GroupRecord | None, new: GroupRecord, acts: tuple[object, ...]) -> list[str]:
    emitted = [
        a.event.reason
        for a in acts
        if isinstance(a, Emit) and a.event.kind is LinkedEventKind.DEGRADED
    ]
    before = prev.degraded_reasons if prev else frozenset[DegradedReason]()
    out = []
    if len(emitted) != len(set(emitted)):
        out.append("I3: duplicate DEGRADED reason in one transition")
    if set(emitted) != set(new.degraded_reasons - before):
        out.append(f"I3: DEGRADED events {emitted} != new reasons {new.degraded_reasons - before}")
    if not before <= new.degraded_reasons:
        out.append("I3: a degraded reason was dropped")
    return out


def _i4_i7(
    prev: GroupRecord | None, new: GroupRecord, acts: tuple[object, ...], closed: bool
) -> list[str]:
    out = []
    for act in acts:
        if isinstance(act, PlaceLeg):
            # I4: never after TRIGGERED or a cancel (explicit or rollback); DEGRADED alone is fine.
            if (
                (prev is None or not can_place(prev))
                or new.winner_leg_index is not None
                or new.cancel_cause is not None
                or new.state in _NEVER_PLACE
            ):
                out.append(f"I4: place_leg while group is {new.state.name}")
            leg = new.legs[act.leg_index]
            if leg.status is not LegStatus.PENDING_CREATE or leg.link_tag is None:
                out.append("I7: place_leg without a write-ahead PENDING_CREATE record")
            if not acts or not isinstance(acts[0], Persist):
                out.append("I7: place_leg not preceded by Persist")
    side_effects = [a for a in acts if not isinstance(a, (Persist, Delete))]
    if side_effects and (prev is None or durable(new) != durable(prev)) and not closed:
        first_is_save = bool(acts) and isinstance(acts[0], (Persist, Delete))
        if not first_is_save and any(not isinstance(a, Emit) for a in side_effects):
            out.append("I7: side effects without a preceding save")
    return out


def _i5(new: GroupRecord) -> list[str]:
    w = new.winner_leg_index
    if w is None:
        return []
    bad = [i for i in link_indices(new) if i != w and i < len(new.legs) and new.legs[i].filled > 0]
    if bad and not (
        new.state is GroupState.DEGRADED and DegradedReason.DOUBLE_FILL in new.degraded_reasons
    ):
        return [f"I5: sibling fill on {bad} without DEGRADED(DOUBLE_FILL)"]
    return []


def _i6_i8(prev: GroupRecord | None, new: GroupRecord) -> list[str]:
    if prev is None:
        return []
    out = []
    if prev.winner_leg_index is not None and new.winner_leg_index != prev.winner_leg_index:
        out.append("I8: winner changed")
    for old, cur in zip(prev.legs, new.legs, strict=False):
        if cur.filled < old.filled:
            out.append(f"I6: leg {old.leg_index} filled went backwards")
        if is_terminal(old) and cur.status is not old.status:
            out.append(f"I6: terminal leg {old.leg_index} changed status")
        if old.status is LegStatus.PARTIALLY_FILLED and cur.status in _REGRESSIVE:
            out.append(f"I6: leg {old.leg_index} went back from PARTIALLY_FILLED")
    return out
