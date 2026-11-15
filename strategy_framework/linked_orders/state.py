"""Pure state machine for emulated linked groups (no I/O, no clock, no logging).

Every public function takes a `GroupRecord` and returns a `Transition`: the new record plus
an ordered tuple of actions for the async shell (`manager.py`) to run. A `Persist` or
`Delete` always comes first, so the record is saved before any side effect is issued.

Leg indices are positions in `spec.ordered_legs()`; `record.legs[i].leg_index == i`. A leg
that will never be submitted gets a NOT_PLACED record (with no link tag) once the group
leaves the states in which legs may still be submitted.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from data_type_primitives import LegRole, LinkKind

from strategy_framework.linked_orders.events import LinkedEventKind, LinkedGroupEvent
from strategy_framework.linked_orders.types import (
    OUTCOME_STATES,
    PLACEMENT_STATES,
    TERMINAL_STATUSES,
    BracketHandle,
    CancelOutcome,
    DegradedReason,
    GroupRecord,
    GroupState,
    LegRecord,
    LegStatus,
    OcoHandle,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from data_type_primitives import LinkedOrderSpec, OrderState

    from strategy_framework.linked_orders.types import (
        GroupId,
        LegFill,
        LegSnapshot,
        LinkTag,
    )

_ZERO = Decimal(0)
_MAX_PASSES = 8
_UNRESOLVED_STATUSES = frozenset({LegStatus.PENDING_CREATE, LegStatus.UNKNOWN})
_REGRESSIVE = frozenset(
    {
        LegStatus.PENDING_CREATE,
        LegStatus.OPEN,
        LegStatus.CREATED,
        LegStatus.APPROVED,
        LegStatus.PENDING_APPROVAL,
    }
)
_CANCEL_UNCERTAIN = frozenset({CancelOutcome.UNKNOWN, CancelOutcome.NOT_FOUND})
_FILLED_STATUSES = frozenset({LegStatus.FILLED, LegStatus.COMPLETED})
_DEAD_STATUSES = frozenset({LegStatus.CANCELED, LegStatus.FAILED})


# --------------------------------------------------------------------------- actions


@dataclass(frozen=True)
class PlaceLeg:
    leg_index: int


@dataclass(frozen=True)
class CancelLeg:
    leg_index: int


@dataclass(frozen=True)
class GetLeg:
    leg_index: int


@dataclass(frozen=True)
class Persist:
    """`store.save(transition.record)`."""


@dataclass(frozen=True)
class Delete:
    """`store.delete(group_id)`: the group is closed (every leg terminal, none unresolved)."""


@dataclass(frozen=True)
class Emit:
    event: LinkedGroupEvent


Action = PlaceLeg | CancelLeg | GetLeg | Persist | Delete | Emit


@dataclass(frozen=True)
class Transition:
    record: GroupRecord
    actions: tuple[Action, ...] = ()


# --------------------------------------------------------------------------- leg rules


def merge_status(old: LegStatus, new: LegStatus) -> LegStatus:
    """Monotonic leg-status rule: terminal never changes, partial never goes back to open."""
    if old in TERMINAL_STATUSES:
        return old
    if old in _UNRESOLVED_STATUSES:
        return new
    if new is LegStatus.PENDING_CREATE:
        return old
    if old is LegStatus.PARTIALLY_FILLED and new in _REGRESSIVE:
        return old
    return new


def merge_filled(old: Decimal, new: Decimal) -> Decimal:
    return max(old, new)


def is_terminal(leg: LegRecord) -> bool:
    return leg.status in TERMINAL_STATUSES


def is_unresolved(leg: LegRecord) -> bool:
    """Status UNKNOWN/PENDING_CREATE, an uncertain cancel, or a fill awaiting `get_leg`."""
    if leg.status in _UNRESOLVED_STATUSES or leg.unresolved_since is not None:
        return True
    return leg.cancel_outcome in _CANCEL_UNCERTAIN and not is_terminal(leg)


def awaiting_reply(leg: LegRecord) -> bool:
    return leg.client_order_id is None and leg.status is LegStatus.PENDING_CREATE


def any_unresolved(record: GroupRecord) -> bool:
    return any(is_unresolved(leg) for leg in record.legs)


def leg_count(record: GroupRecord) -> int:
    return len(record.spec.legs)


def link_indices(record: GroupRecord) -> range:
    """Link legs: all legs for OCO, the exits for BRACKET."""
    start = 1 if record.spec.kind is LinkKind.BRACKET else 0
    return range(start, leg_count(record))


def find_leg(record: GroupRecord, client_order_id: str) -> int | None:
    for leg in record.legs:
        if leg.client_order_id == client_order_id:
            return leg.leg_index
    return None


def can_place(record: GroupRecord) -> bool:
    """I4: legs may be submitted only in PLACING / EXITS_PLACING, with no winner or cancel."""
    return (
        record.state in (GroupState.PLACING, GroupState.EXITS_PLACING)
        and record.winner_leg_index is None
        and record.cancel_cause is None
    )


def residual_filled(record: GroupRecord) -> Decimal:
    """Entry fill (BRACKET) plus winner fill: the exposure left after a cancel."""
    total = _ZERO
    if record.spec.kind is LinkKind.BRACKET and record.legs:
        total += record.legs[0].filled
    if record.winner_leg_index is not None:
        total += record.legs[record.winner_leg_index].filled
    return total


class FillIntake:
    """Bounded intake filter: cumulative fills must grow, and a `fill_id` is seen once."""

    def __init__(self, max_seen: int = 4096) -> None:
        self._max = max_seen
        self._seen: dict[tuple[str, str], None] = {}

    def accept(self, fill: LegFill, recorded_filled: Decimal) -> bool:
        if fill.cumulative_filled <= recorded_filled:
            return False
        if fill.fill_id is None:
            return True
        key = (fill.client_order_id, fill.fill_id)
        if key in self._seen:
            return False
        self._seen[key] = None
        if len(self._seen) > self._max:
            del self._seen[next(iter(self._seen))]
        return True


# --------------------------------------------------------------------------- context


class _Ctx:
    """Mutable scratch space for one transition; never escapes this module."""

    def __init__(self, record: GroupRecord, now: float, *, closed: bool = False) -> None:
        self.orig = record
        self.rec = record
        self.now = now
        self.closed = closed
        self.effects: list[Action] = []
        self.delete = False
        self.hint: int | None = None

    # -- primitives

    def set_leg(self, index: int, **changes: Any) -> None:
        legs = list(self.rec.legs)
        legs[index] = replace(legs[index], **changes)
        self.rec = replace(self.rec, legs=tuple(legs))

    def event(self, kind: LinkedEventKind, **fields: Any) -> None:
        r = self.rec
        self.effects.append(
            Emit(
                LinkedGroupEvent(
                    kind=kind,
                    group_id=str(r.group_id),
                    link_kind=r.spec.kind,
                    target=r.target,
                    state=r.state,
                    timestamp=self.now,
                    client_order_ids=tuple(leg.client_order_id for leg in r.legs),
                    filled=tuple(leg.filled for leg in r.legs),
                    **fields,
                )
            )
        )

    def seal(self) -> None:
        """Record every never-submitted leg as NOT_PLACED."""
        r = self.rec
        specs = r.spec.ordered_legs()
        if len(r.legs) >= len(specs):
            return
        extra = tuple(
            LegRecord(i, specs[i].role, None, None, LegStatus.NOT_PLACED, _ZERO, _ZERO)
            for i in range(len(r.legs), len(specs))
        )
        self.rec = replace(r, legs=r.legs + extra)

    def enter(self, state: GroupState) -> None:
        self.rec = replace(self.rec, state=state)
        if state not in PLACEMENT_STATES:
            self.seal()

    def degrade(
        self, reason: DegradedReason, *, leg_index: int | None = None, detail: str = ""
    ) -> None:
        if reason in self.rec.degraded_reasons:
            return
        self.rec = replace(self.rec, degraded_reasons=self.rec.degraded_reasons | {reason})
        self.enter(GroupState.DEGRADED)
        self.event(LinkedEventKind.DEGRADED, reason=reason, leg_index=leg_index, detail=detail)

    # -- leg merge

    def merge(self, index: int, status: LegStatus, filled: Decimal, *, confirmed: bool) -> bool:
        """Apply a status/fill under the monotonic rule. Returns True if the leg changed."""
        leg = self.rec.legs[index]
        new_status = merge_status(leg.status, status)
        new_filled = merge_filled(leg.filled, filled)
        if not confirmed and new_status is leg.status and new_filled == leg.filled:
            return False
        term = new_status in TERMINAL_STATUSES
        zero_fill_done = new_status in _FILLED_STATUSES and new_filled == _ZERO
        cancel_outcome, cancel_requested = leg.cancel_outcome, leg.cancel_requested
        if confirmed:
            if cancel_outcome in _CANCEL_UNCERTAIN:
                cancel_outcome = None
                cancel_requested = cancel_requested and term
            awaiting = new_status in _UNRESOLVED_STATUSES or zero_fill_done
        else:
            is_entry = self.rec.spec.kind is LinkKind.BRACKET and index == 0
            entry_pending = is_entry and term and (not is_terminal(leg) or new_filled > leg.filled)
            uncertain_cancel = cancel_outcome in _CANCEL_UNCERTAIN and not term
            awaiting = (
                new_status in _UNRESOLVED_STATUSES
                or uncertain_cancel
                or entry_pending
                or zero_fill_done
            )
        changed = new_status is not leg.status or new_filled != leg.filled
        self.set_leg(
            index,
            status=new_status,
            filled=new_filled,
            cancel_outcome=cancel_outcome,
            cancel_requested=cancel_requested,
            unresolved_since=(leg.unresolved_since or self.now) if awaiting else None,
        )
        if awaiting and term and not confirmed:
            self.effects.append(GetLeg(index))
        if (
            index in link_indices(self.rec)
            and new_filled > _ZERO
            and self.rec.winner_leg_index is None
            and self.hint is None
        ):
            self.hint = index
        if changed:
            self.event(LinkedEventKind.LEG_UPDATED, leg_index=index)
        return changed

    # -- settle: run every deferred rule until nothing changes

    def settle(self) -> None:
        for _ in range(_MAX_PASSES):
            before = self.rec
            self._stamp()
            self._trigger()
            self._double_fill()
            self._dispatch_cancels()
            self._progress()
            if self.rec == before:
                break
        self._close()

    def _stamp(self) -> None:
        for leg in self.rec.legs:
            if leg.unresolved_since is None and is_unresolved(leg):
                self.set_leg(leg.leg_index, unresolved_since=self.now)

    def _trigger(self) -> None:
        r = self.rec
        if r.winner_leg_index is not None:
            return
        filled = [i for i in link_indices(r) if i < len(r.legs) and r.legs[i].filled > _ZERO]
        if not filled:
            return
        winner = self.hint if self.hint is not None and self.hint in filled else min(filled)
        self.rec = replace(r, winner_leg_index=winner)
        if r.state in (GroupState.PLACING, GroupState.ARMED, GroupState.EXITS_PLACING):
            deferred = any_unresolved(self.rec)
            self.enter(GroupState.TRIGGERED)
            self.event(LinkedEventKind.TRIGGERED, leg_index=winner, deferred=deferred)

    def _double_fill(self) -> None:
        r = self.rec
        winner = r.winner_leg_index
        if winner is None or DegradedReason.DOUBLE_FILL in r.degraded_reasons:
            return
        bad = [
            i
            for i in link_indices(r)
            if i != winner and i < len(r.legs) and r.legs[i].filled > _ZERO
        ]
        if bad:
            self.degrade(
                DegradedReason.DOUBLE_FILL,
                leg_index=bad[0],
                detail=f"winner leg {winner} and sibling leg(s) {bad} both filled",
            )

    def _dispatch_cancels(self) -> None:
        r = self.rec
        cause, winner = r.cancel_cause, r.winner_leg_index
        if cause is None and winner is None:
            return
        if cause != "user" and any_unresolved(r):
            return
        if cause is None:
            pool = [i for i in link_indices(r) if i != winner]
        else:
            pool = list(range(len(r.legs)))
        for i in pool:
            leg = r.legs[i]
            if is_terminal(leg) or leg.client_order_id is None or leg.cancel_requested:
                continue
            if is_unresolved(leg):
                continue
            self.set_leg(i, cancel_requested=True)
            self.effects.append(CancelLeg(i))

    def _progress(self) -> None:
        state = self.rec.state
        if state is GroupState.PLACING:
            self._arm_after_placing()
        elif state is GroupState.ENTRY_WORKING:
            self._entry_done()
        elif state is GroupState.EXITS_PLACING:
            self._arm_after_exits()
        elif state is GroupState.TRIGGERED:
            self._maybe_complete()
        elif state is GroupState.CANCELLING:
            self._maybe_finish_cancel()
        elif state is GroupState.ARMED:
            self._link_broken()

    def _all_submitted(self) -> bool:
        r = self.rec
        return len(r.legs) == leg_count(r) and not any(awaiting_reply(leg) for leg in r.legs)

    def _arm_after_placing(self) -> None:
        r = self.rec
        if r.spec.kind is LinkKind.OCO:
            if self._all_submitted():
                self.enter(GroupState.ARMED)
                self.event(LinkedEventKind.PLACED)
        elif r.legs and not awaiting_reply(r.legs[0]):
            self.enter(GroupState.ENTRY_WORKING)
            self.event(LinkedEventKind.PLACED)

    def _arm_after_exits(self) -> None:
        if self._all_submitted():
            self.enter(GroupState.ARMED)
            self.event(LinkedEventKind.PLACED)

    def _entry_done(self) -> None:
        entry = self.rec.legs[0]
        if self.rec.cancel_cause is not None or not is_terminal(entry) or is_unresolved(entry):
            return
        if entry.filled > _ZERO:
            self.enter(GroupState.EXITS_PLACING)
        elif entry.status is LegStatus.CANCELED:
            self.enter(GroupState.CANCELED)
            self.event(LinkedEventKind.CANCELED, residual_filled=_ZERO)
        elif entry.status is LegStatus.FAILED:
            self.enter(GroupState.FAILED)
            self.event(LinkedEventKind.FAILED, residual_filled=_ZERO)

    def _maybe_complete(self) -> None:
        r = self.rec
        if any_unresolved(r):
            return
        for i in link_indices(r):
            if i != r.winner_leg_index and not (
                is_terminal(r.legs[i]) and r.legs[i].filled == _ZERO
            ):
                return
        self.enter(GroupState.COMPLETED)
        self.event(LinkedEventKind.COMPLETED, residual_filled=residual_filled(r))

    def _maybe_finish_cancel(self) -> None:
        r = self.rec
        if any_unresolved(r) or not all(is_terminal(leg) for leg in r.legs):
            return
        if r.cancel_cause == "user":
            self.enter(GroupState.CANCELED)
            self.event(LinkedEventKind.CANCELED, residual_filled=residual_filled(r))
        else:
            self.enter(GroupState.FAILED)
            self.event(LinkedEventKind.FAILED, residual_filled=residual_filled(r))

    def _link_broken(self) -> None:
        r = self.rec
        dead = [
            i
            for i in link_indices(r)
            if r.legs[i].status in _DEAD_STATUSES
            and not r.legs[i].cancel_requested
            and r.legs[i].filled == _ZERO
        ]
        if not dead:
            return
        live = [i for i in link_indices(r) if not is_terminal(r.legs[i])]
        if len(live) <= 1:
            self.degrade(
                DegradedReason.LINK_BROKEN,
                leg_index=dead[0],
                detail=f"link leg(s) {dead} ended externally; {len(live)} link leg(s) remain",
            )

    def _close(self) -> None:
        r = self.rec
        if self.closed or (r.state not in OUTCOME_STATES and r.state is not GroupState.DEGRADED):
            return
        if len(r.legs) != leg_count(r) or any_unresolved(r):
            return
        if not all(is_terminal(leg) for leg in r.legs):
            return
        self.delete = True
        self.event(LinkedEventKind.CLOSED)

    # -- result

    def finish(self) -> Transition:
        changed = self.rec != self.orig
        head: list[Action] = []
        if self.delete:
            head.append(Delete())
        elif changed:
            reopened = self.rec.degraded_reasons != self.orig.degraded_reasons
            if not self.closed or reopened:
                head.append(Persist())
        return Transition(self.rec, tuple(head) + tuple(self.effects))


def _run(record: GroupRecord, now: float, closed: bool, body: Callable[[_Ctx], None]) -> Transition:
    ctx = _Ctx(record, now, closed=closed)
    body(ctx)
    ctx.settle()
    return ctx.finish()


# --------------------------------------------------------------------------- public API


def new_group(group_id: GroupId, target: str, spec: LinkedOrderSpec, now: float) -> GroupRecord:
    """Row 1: a fresh PLACING group with no legs (the caller saves it: write-ahead)."""
    return GroupRecord(
        group_id=group_id, target=target, spec=spec, state=GroupState.PLACING, created_at=now
    )


def begin_leg(record: GroupRecord, leg_index: int, link_tag: LinkTag, now: float) -> Transition:
    """Rows 2/13: write-ahead the next leg as PENDING_CREATE, then `PlaceLeg`.

    Bracket exits are sized `min(exit.amount, entry.filled)`.
    """
    if not can_place(record):
        msg = f"cannot place a leg while group is {record.state.name}"
        raise ValueError(msg)
    if leg_index != len(record.legs) or leg_index >= leg_count(record):
        msg = f"legs must be submitted in order; got {leg_index} after {len(record.legs)}"
        raise ValueError(msg)
    bracket = record.spec.kind is LinkKind.BRACKET
    if bracket and (record.state is GroupState.PLACING) != (leg_index == 0):
        msg = "a BRACKET places its entry first, then its exits"
        raise ValueError(msg)
    spec_leg = record.spec.ordered_legs()[leg_index]
    amount = spec_leg.amount
    if record.state is GroupState.EXITS_PLACING:
        amount = min(amount, record.legs[0].filled)
    leg = LegRecord(
        leg_index,
        spec_leg.role,
        link_tag,
        None,
        LegStatus.PENDING_CREATE,
        _ZERO,
        amount,
        unresolved_since=now,
    )
    return Transition(replace(record, legs=(*record.legs, leg)), (Persist(), PlaceLeg(leg_index)))


def leg_placed(
    record: GroupRecord, leg_index: int, client_order_id: str, now: float, *, closed: bool = False
) -> Transition:
    """`place_leg` returned: register the id (the leg is OPEN until a report says otherwise)."""

    def body(ctx: _Ctx) -> None:
        leg = ctx.rec.legs[leg_index]
        pending = leg.status is LegStatus.PENDING_CREATE
        ctx.set_leg(
            leg_index,
            client_order_id=client_order_id,
            status=LegStatus.OPEN if pending else leg.status,
            unresolved_since=None if pending else leg.unresolved_since,
        )

    return _run(record, now, closed, body)


def leg_unknown(
    record: GroupRecord, leg_index: int, client_order_id: str, now: float, *, closed: bool = False
) -> Transition:
    """Row 5: `OrderOutcomeUnknownError`; the leg is UNKNOWN and unresolved."""

    def body(ctx: _Ctx) -> None:
        leg = ctx.rec.legs[leg_index]
        ctx.set_leg(
            leg_index,
            client_order_id=client_order_id,
            status=LegStatus.UNKNOWN,
            unresolved_since=leg.unresolved_since or now,
        )

    return _run(record, now, closed, body)


def leg_rejected(
    record: GroupRecord, leg_index: int, now: float, *, closed: bool = False
) -> Transition:
    """Rows 7/15: a definite placement error. No retry, ever."""

    def body(ctx: _Ctx) -> None:
        ctx.set_leg(leg_index, status=LegStatus.FAILED, unresolved_since=None)
        state = ctx.rec.state
        if state is GroupState.PLACING:
            ctx.rec = replace(ctx.rec, cancel_cause="rollback")
            ctx.enter(GroupState.CANCELLING)
        elif state is GroupState.EXITS_PLACING:
            ctx.degrade(
                DegradedReason.EXIT_PLACEMENT_FAILED,
                leg_index=leg_index,
                detail="exit rejected: the position is unprotected or only partially protected",
            )

    return _run(record, now, closed, body)


def apply_update(
    record: GroupRecord,
    client_order_id: str,
    new_state: OrderState,
    now: float,
    *,
    closed: bool = False,
) -> Transition:
    """Row 6/24: an order-state report. Unknown ids and stale reports change nothing."""
    index = find_leg(record, client_order_id)
    if index is None:
        return Transition(record)

    def body(ctx: _Ctx) -> None:
        ctx.merge(index, LegStatus.from_order_state(new_state), _ZERO, confirmed=False)

    return _run(record, now, closed, body)


def apply_fill(
    record: GroupRecord, fill: LegFill, now: float, *, closed: bool = False
) -> Transition:
    """Rows 8/11/18/24: a cumulative fill report; only growth is applied."""
    index = find_leg(record, fill.client_order_id)
    if index is None or fill.cumulative_filled <= record.legs[index].filled:
        return Transition(record)
    status = (
        LegStatus.FILLED
        if fill.cumulative_filled >= record.legs[index].placed_amount
        else LegStatus.PARTIALLY_FILLED
    )

    def body(ctx: _Ctx) -> None:
        ctx.merge(index, status, fill.cumulative_filled, confirmed=False)

    return _run(record, now, closed, body)


def apply_snapshot(
    record: GroupRecord,
    leg_index: int,
    snapshot: LegSnapshot | None,
    now: float,
    *,
    closed: bool = False,
) -> Transition:
    """Row 6/21: a `get_leg` answer. A snapshot confirms; None is not proof of anything."""

    def body(ctx: _Ctx) -> None:
        if snapshot is None:
            ctx.merge(leg_index, LegStatus.UNKNOWN, _ZERO, confirmed=False)
            return
        if ctx.rec.legs[leg_index].client_order_id is None:
            ctx.set_leg(leg_index, client_order_id=snapshot.client_order_id)
        ctx.merge(
            leg_index,
            LegStatus.from_order_state(snapshot.state),
            snapshot.filled,
            confirmed=True,
        )

    return _run(record, now, closed, body)


def apply_cancel_outcome(
    record: GroupRecord,
    leg_index: int,
    outcome: CancelOutcome,
    now: float,
    *,
    closed: bool = False,
) -> Transition:
    """The venue's answer to `cancel_leg`. NOT_FOUND/UNKNOWN leave the leg unresolved."""

    def body(ctx: _Ctx) -> None:
        leg = ctx.rec.legs[leg_index]
        ctx.set_leg(leg_index, cancel_requested=True, cancel_outcome=outcome)
        if outcome is CancelOutcome.CANCELED:
            ctx.merge(leg_index, LegStatus.CANCELED, _ZERO, confirmed=False)
        elif outcome is CancelOutcome.ALREADY_FILLED:
            ctx.merge(
                leg_index, LegStatus.FILLED, max(leg.filled, leg.placed_amount), confirmed=False
            )

    return _run(record, now, closed, body)


def request_cancel(record: GroupRecord, now: float, *, closed: bool = False) -> Transition:
    """Row 17: user cancel. Live legs are cancelled now, unresolved ones when they resolve."""
    if record.state in OUTCOME_STATES or record.cancel_cause is not None:
        return Transition(record)

    def body(ctx: _Ctx) -> None:
        ctx.rec = replace(ctx.rec, cancel_cause="user")
        if ctx.rec.state is not GroupState.DEGRADED:
            ctx.enter(GroupState.CANCELLING)
        ctx.seal()

    return _run(record, now, closed, body)


def tick(record: GroupRecord, now: float, grace_period_s: float) -> Transition:
    """Rows 20/21: grace check and `get_leg` retries for every unresolved leg."""
    ctx = _Ctx(record, now)
    ctx.settle()
    unresolved = [leg for leg in ctx.rec.legs if is_unresolved(leg)]
    if any(now - (leg.unresolved_since or now) > grace_period_s for leg in unresolved):
        ctx.degrade(
            DegradedReason.UNRESOLVED_PAST_GRACE,
            detail=f"leg(s) {[leg.leg_index for leg in unresolved]} unresolved past grace",
        )
        ctx.settle()
    ctx.effects.extend(GetLeg(leg.leg_index) for leg in unresolved if leg.client_order_id)
    return ctx.finish()


def make_handle(record: GroupRecord) -> OcoHandle | BracketHandle:
    """Fresh snapshot handle. Ids of unplaced, NOT_PLACED or rejected legs are None."""
    specs = record.spec.ordered_legs()
    ids: list[str | None] = [None] * len(specs)
    for leg in record.legs:
        ids[leg.leg_index] = None if leg.status is LegStatus.NOT_PLACED else leg.client_order_id
    group_id = str(record.group_id)
    if record.spec.kind is LinkKind.OCO:
        return OcoHandle(group_id, tuple(ids), record.state)
    by_role = {leg.role: ids[i] for i, leg in enumerate(specs)}
    return BracketHandle(
        group_id,
        by_role[LegRole.ENTRY],
        by_role.get(LegRole.TAKE_PROFIT),
        by_role.get(LegRole.STOP_LOSS),
        record.state,
    )
