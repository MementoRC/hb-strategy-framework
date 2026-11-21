"""Opt-in emulated linked orders (OCO / BRACKET) on venues without native support.

Each leg is placed as the venue's own native order type; the manager emulates only the *link*:
when one leg fills it cancels the siblings. The decisions live in `state.py` (pure functions);
this module is the async shell that runs the actions they return.

Hazards (read before enabling)
------------------------------
* **Double fill.** Emulation is not atomic and cannot give native OCA guarantees. A sibling can
  fill before the cancel lands, while the process is down or the stream is lost, while a cancel
  is deferred on an unresolved leg, or as a late CANCELED-with-fill report. The manager detects
  this (group goes DEGRADED with `DOUBLE_FILL`, event + WARNING log) but never prevents it and
  never places compensating orders (no auto-unwind).
* **Unprotected window (BRACKET).** Exits are placed only after the entry is terminal and its
  final fill is confirmed by `get_leg`, sized `min(exit.amount, filled)`. The filled part of a
  partially filled entry has no protection until the exits are acknowledged. Limit the window by
  the choice of entry type and by calling `cancel_linked` (which never places exits).
* **Rejected exit.** If one exit is rejected (for example after resizing below the venue minimum)
  the group goes DEGRADED(`EXIT_PLACEMENT_FAILED`), nothing is retried, and the remaining exits
  are still placed. The position is unprotected or only partially protected.
* **Durable store required.** The write-ahead record is what lets `recover()` find legs after a
  crash. A non-durable store is refused unless `config.allow_volatile_store` is set.

Concurrency: every state change of a group happens under that group's `asyncio.Lock`; the lock is
never held across a venue call. Updates and fills for an id that is not registered yet (including
a leg whose `place_leg` reply is still pending) go to a bounded buffer and are replayed, in
arrival order, before any trigger or cancel is evaluated. The manager starts no background tasks:
the caller feeds `on_order_update` / `on_fill` and calls `tick()` periodically.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field, replace
from decimal import Decimal
from typing import TYPE_CHECKING, cast

from data_type_primitives import LinkKind, OrderOutcomeUnknownError

from strategy_framework.linked_orders.errors import (
    EmulationNotEnabledError,
    GroupIdPersistenceError,
    GroupIdSpaceExhaustedError,
    GroupInvariantError,
    LinkedGroupNotFoundError,
    LinkIdCodecError,
    RecoveryRequiredError,
    UnsupportedLegError,
    VolatileStoreError,
)
from strategy_framework.linked_orders.events import (
    LINKED_GROUP_EVENT,
    LinkedEventKind,
    LinkedGroupEvent,
)
from strategy_framework.linked_orders.protocols import (
    BoundedLinkIdCodec,
    GroupIdHighWaterStore,
)
from strategy_framework.linked_orders.state import (
    CancelLeg,
    Delete,
    Emit,
    FillIntake,
    GetLeg,
    Persist,
    apply_cancel_outcome,
    apply_fill,
    apply_snapshot,
    apply_update,
    begin_leg,
    can_place,
    cancel_status,
    cancel_still_due,
    durable,
    find_leg,
    is_terminal,
    leg_cancel_outcomes,
    leg_count,
    leg_placed,
    leg_rejected,
    leg_unknown,
    make_handle,
    mark_link_broken,
    new_group,
    request_cancel,
    residual_filled,
    resume,
    tick,
    withdraw_cancel,
)
from strategy_framework.linked_orders.store import InMemoryLinkedGroupStore
from strategy_framework.linked_orders.types import (
    CancelOutcome,
    GroupState,
    LegFill,
    LegStatus,
    LinkedCancelOutcome,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from data_type_primitives import LegSpec, LinkedOrderSpec, OrderState, OrderUpdate

    from strategy_framework.linked_orders.config import LinkedOrderManagerConfig
    from strategy_framework.linked_orders.protocols import (
        ClockProtocol,
        EmulationVenue,
        LinkedEventEmitter,
        LinkedGroupStore,
        LinkedOrderIdCodec,
    )
    from strategy_framework.linked_orders.state import Transition
    from strategy_framework.linked_orders.types import (
        BracketHandle,
        GroupId,
        GroupRecord,
        LegSnapshot,
        LinkTag,
        OcoHandle,
    )

logger = logging.getLogger(__name__)

_WARNED_KINDS = frozenset({LinkedEventKind.DEGRADED, LinkedEventKind.SHUTDOWN_OPEN})
_PLACEABLE_STATUSES = frozenset({LegStatus.PENDING_CREATE, LegStatus.UNKNOWN})

_IoAction = CancelLeg | GetLeg

_GROUP_ID_EPOCH = 1_767_225_600  # 2026-01-01T00:00:00Z: origin of the time-derived id floor


class _SystemClock:
    def time(self) -> float:
        return time.time()


@dataclass
class _Group:
    """Runtime wrapper around a `GroupRecord` (the record itself is persisted state)."""

    record: GroupRecord
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    closed: bool = False
    closed_at: float = 0.0
    driving: bool = False
    drive_pending: bool = False
    inflight: set[int] = field(default_factory=set)
    getting: set[int] = field(default_factory=set)  # legs with a `get_leg` call outstanding


@dataclass(frozen=True)
class _Buffered:
    at: float
    client_order_id: str
    item: OrderState | LegFill


class EmulatedLinkedOrderManager:
    """Consumer-side emulation of OCO / BRACKET over a venue's native single orders.

    **Emulated OCO cannot give native OCA guarantees**: a sibling can fill before its cancel
    lands (double fill). That is detected and reported, never prevented or unwound. A BRACKET
    has an **unprotected window**: its exits are placed once, after the entry is terminal and
    its fill is confirmed, so a partially filled entry is unprotected until then. See the module
    docstring for the full list of hazards.

    `place_*` returns once submission is done; the group can already be FAILED, TRIGGERED or
    DEGRADED. Callers MUST check `handle.state` and subscribe to `"linked.group"` events for
    later changes. Handles are snapshots; use `get_handle` for a fresh one.

    `shutdown()` persists and reports open groups; it never cancels (the legs stay live).
    """

    def __init__(
        self,
        venue: EmulationVenue,
        codec: LinkedOrderIdCodec,
        config: LinkedOrderManagerConfig,
        *,
        store: LinkedGroupStore | None = None,
        clock: ClockProtocol | None = None,
        bus: LinkedEventEmitter | None = None,
    ) -> None:
        if not config.enabled:
            raise EmulationNotEnabledError
        self._venue = venue
        self._codec = codec
        self._config = config
        self._store: LinkedGroupStore = store if store is not None else InMemoryLinkedGroupStore()
        self._clock: ClockProtocol = clock if clock is not None else _SystemClock()
        self._bus = bus
        self._groups: dict[GroupId, _Group] = {}
        self._by_cid: dict[str, GroupId] = {}
        self._buffer: deque[_Buffered] = deque()
        self._intake = FillIntake()
        self._recovered = False
        self._next_id = 0
        self._next_id = self._checked_lower_bound()

    # ------------------------------------------------------------------ public API

    @property
    def has_pending_orders(self) -> bool:
        return any(not group.closed for group in self._groups.values())

    async def place_oco(
        self, target: str, spec: LinkedOrderSpec, *, options: Mapping[str, object] | None = None
    ) -> OcoHandle:
        group = await self._place(target, spec, LinkKind.OCO, options)
        return cast("OcoHandle", make_handle(group.record))

    async def place_bracket(
        self, target: str, spec: LinkedOrderSpec, *, options: Mapping[str, object] | None = None
    ) -> BracketHandle:
        group = await self._place(target, spec, LinkKind.BRACKET, options)
        return cast("BracketHandle", make_handle(group.record))

    def get_handle(self, group_id: str) -> OcoHandle | BracketHandle:
        return make_handle(self._require(group_id).record)

    async def cancel_linked(self, handle: OcoHandle | BracketHandle) -> LinkedCancelOutcome:
        group = self._require(handle.group_id)
        async with group.lock:
            trans = request_cancel(group.record, self._now(), closed=group.closed)
            io = self._commit(group, trans)
        await self._after(group, io)
        rec = group.record
        if not rec.legs:
            raise GroupInvariantError(rec.group_id, "cancel_linked on a group with no legs")
        all_terminal = len(rec.legs) == leg_count(rec) and all(is_terminal(leg) for leg in rec.legs)
        return LinkedCancelOutcome(
            group_id=handle.group_id,
            state=rec.state,
            all_legs_terminal=all_terminal,
            residual_filled=residual_filled(rec),
            leg_outcomes=leg_cancel_outcomes(rec),
            status=cancel_status(rec.state, all_legs_terminal=all_terminal),
        )

    async def on_order_update(self, update: OrderUpdate) -> None:
        cid = update.client_order_id
        if cid is None:
            return
        group = self._group_for(cid)
        if group is None:
            self._buffer_add(cid, update.new_state)
            return
        async with group.lock:
            trans = apply_update(
                group.record, cid, update.new_state, self._now(), closed=group.closed
            )
            io = self._commit(group, trans)
        await self._after(group, io)

    async def on_fill(self, fill: LegFill) -> None:
        group = self._group_for(fill.client_order_id)
        if group is None:
            self._buffer_add(fill.client_order_id, fill)
            return
        async with group.lock:
            index = find_leg(group.record, fill.client_order_id)
            if index is None or not self._intake.accept(fill, group.record.legs[index].filled):
                return
            trans = apply_fill(group.record, fill, self._now(), closed=group.closed)
            io = self._commit(group, trans)
        await self._after(group, io)

    async def tick(self) -> None:
        """Grace timer, `get_leg`/cancel retries, buffer and tombstone TTLs."""
        now = self._now()
        self._expire_buffer(now)
        for group in list(self._groups.values()):
            if group.closed:
                if now - group.closed_at > self._config.tombstone_ttl_s:
                    self._purge(group)
                continue
            async with group.lock:
                trans = tick(group.record, now, self._config.grace_period_s, self._config.retry)
                io = self._commit(group, trans)
            await self._after(group, io)

    async def recover(self, targets: Sequence[str]) -> None:
        """Reconcile the store with the venue in both directions (restart recovery)."""
        now = self._now()
        groups = [self._load(record, now) for record in self._store.load_all()]
        for group in groups:
            await self._reconcile_store_to_venue(group)
        orphans = await self._reconcile_venue_to_store(targets)
        for group in groups:
            await self._resume(group)
        self._seed_counter()
        self._recovered = True
        degraded = sum(1 for g in groups if g.record.state is GroupState.DEGRADED)
        self._emit(
            LinkedGroupEvent(
                kind=LinkedEventKind.RECOVERED,
                group_id="",
                link_kind=None,
                target=",".join(targets),
                state=None,
                timestamp=self._now(),
                detail=(
                    f"groups={len(groups)} degraded={degraded} orphans={len(orphans)} "
                    f"resumed={len(groups) - degraded}"
                ),
            )
        )

    async def shutdown(self) -> None:
        """Persist and report every open group. NEVER cancels: the legs stay live."""
        for group in list(self._groups.values()):
            if group.closed:
                continue
            async with group.lock:
                self._store.save(durable(group.record))
                self._emit(
                    self._event(
                        LinkedEventKind.SHUTDOWN_OPEN,
                        group.record,
                        "manager shut down; the legs stay live on the venue",
                    )
                )

    # ------------------------------------------------------------------ placement

    async def _place(
        self,
        target: str,
        spec: LinkedOrderSpec,
        kind: LinkKind,
        options: Mapping[str, object] | None,
    ) -> _Group:
        if self._config.require_recover_before_place and not self._recovered:
            raise RecoveryRequiredError
        if not (self._store.durable or self._config.allow_volatile_store):
            raise VolatileStoreError
        if spec.kind is not kind:
            msg = f"spec.kind is {spec.kind.name}, but a {kind.name} was requested"
            raise ValueError(msg)
        if options:
            logger.debug("emulated linked orders ignore options: %s", sorted(options))
        for index, leg in enumerate(spec.ordered_legs()):
            if not self._venue.supports_leg(target, leg):
                raise UnsupportedLegError(index, leg.role, leg.order_type)
        group_id = self._checked_lower_bound()  # no await until _next_id is advanced: atomic
        self._check_codec(group_id, spec)  # places nothing: a rejected id must not reach the HWM
        self._persist_hwm(group_id)  # fail closed: before the id reaches the venue
        self._next_id = group_id + 1
        record = new_group(group_id, target, spec, self._now())
        self._store.save(record)  # write-ahead: the group exists before any leg
        group = _Group(record)
        self._groups[group_id] = group
        await self._drive(group)
        return group

    def _lower_bound(self) -> GroupId:
        """Smallest id that can never have been used: max of the counter, seed, HWM and floor."""
        return max(self._bound_components().values())

    def _bound_components(self) -> dict[str, int]:
        bounds = {
            "counter": self._next_id,
            "seed": self._config.group_id_seed,
            "time floor": self._time_floor(),
        }
        if isinstance(self._store, GroupIdHighWaterStore):
            hwm = self._store.load_group_id_hwm()
            if hwm is not None:
                bounds["HWM"] = hwm + 1
        return bounds

    def _checked_lower_bound(self) -> GroupId:
        """`_lower_bound`, raising instead of exceeding a bounded codec's id space."""
        bounds = self._bound_components()
        lower = max(bounds.values())
        if isinstance(self._codec, BoundedLinkIdCodec) and lower > self._codec.max_group_id:
            dominant = max(bounds, key=lambda name: bounds[name])
            raise GroupIdSpaceExhaustedError(lower, self._codec.max_group_id, dominant)
        return lower

    def _time_floor(self) -> int:
        factor = self._config.group_id_time_factor
        return max(0, (int(self._now()) - _GROUP_ID_EPOCH) * factor)

    def _persist_hwm(self, group_id: GroupId) -> None:
        if not isinstance(self._store, GroupIdHighWaterStore):
            return
        try:
            self._store.save_group_id_hwm(group_id)
        except Exception as exc:
            raise GroupIdPersistenceError(group_id) from exc

    def _check_codec(self, group_id: GroupId, spec: LinkedOrderSpec) -> None:
        for index in range(len(spec.legs)):
            try:
                tag = self._codec.encode(group_id, index)
            except Exception as exc:
                raise LinkIdCodecError(group_id, index, None) from exc
            try:
                decoded = self._codec.decode(tag)
            except Exception as exc:
                raise LinkIdCodecError(group_id, index, tag) from exc
            if decoded != (group_id, index):
                raise LinkIdCodecError(group_id, index, tag)

    async def _drive(self, group: _Group) -> None:
        """Submit legs one at a time while the state machine allows it."""
        group.driving = True
        try:
            while (step := await self._begin_next(group)) is not None:
                await self._submit(group, *step)
        finally:
            group.driving = False

    async def _begin_next(self, group: _Group) -> tuple[int, LegSpec, LinkTag] | None:
        async with group.lock:
            rec = group.record
            index = len(rec.legs)
            entry_only = rec.spec.kind is LinkKind.BRACKET and rec.state is GroupState.PLACING
            if not can_place(rec) or index >= leg_count(rec) or (entry_only and index >= 1):
                return None
            tag = self._codec.encode(rec.group_id, index)
            trans = begin_leg(rec, index, tag, self._now())
            self._commit(group, trans)
            group.drive_pending = False
            group.inflight.add(index)
            leg = group.record.legs[index]
            spec_leg = rec.spec.ordered_legs()[index]
            if leg.placed_amount != spec_leg.amount:
                spec_leg = spec_leg.model_copy(update={"amount": leg.placed_amount})
            return index, spec_leg, tag

    async def _submit(self, group: _Group, index: int, leg: LegSpec, tag: LinkTag) -> None:
        reply: str | OrderOutcomeUnknownError | None
        try:
            reply = await self._venue.place_leg(group.record.target, leg, link_tag=tag)
        except OrderOutcomeUnknownError as exc:
            reply = exc
        except Exception:
            logger.warning("place_leg rejected for group %s leg %s", group.record.group_id, index)
            reply = None
        async with group.lock:
            group.inflight.discard(index)
            io = self._register_reply(group, index, reply)
        await self._exec(group, io)

    def _register_reply(
        self, group: _Group, index: int, reply: str | OrderOutcomeUnknownError | None
    ) -> list[_IoAction]:
        rec, now = group.record, self._now()
        if reply is None:
            return self._commit(group, leg_rejected(rec, index, now, closed=group.closed))
        unknown = isinstance(reply, OrderOutcomeUnknownError)
        cid = reply.client_order_id if isinstance(reply, OrderOutcomeUnknownError) else reply
        if cid is None:  # lost reply with no id: stays PENDING_CREATE until a tag lookup
            return []
        replay = self._take_buffered(cid)
        make = leg_unknown if unknown else leg_placed
        trans = make(rec, index, cid, now, closed=group.closed, replay=replay)
        return self._commit(group, trans)

    # ------------------------------------------------------------------ action execution

    def _commit(self, group: _Group, trans: Transition) -> list[_IoAction]:
        """Adopt a transition (call under the group lock): persist, emit, collect venue I/O."""
        prev_state = group.record.state
        group.record = trans.record
        io: list[_IoAction] = []
        reopened = False
        for act in trans.actions:
            if isinstance(act, Persist):
                self._store.save(durable(trans.record))
                reopened = group.closed
            elif isinstance(act, Delete):
                self._store.delete(trans.record.group_id)
                group.closed, group.closed_at = True, self._now()
            elif isinstance(act, Emit):
                self._emit(act.event)
            elif isinstance(act, (CancelLeg, GetLeg)):
                io.append(act)
        if reopened:
            group.closed = False
        for leg in trans.record.legs:
            if leg.client_order_id is not None:
                self._by_cid[leg.client_order_id] = trans.record.group_id
        if prev_state is not GroupState.EXITS_PLACING and trans.record.state is (
            GroupState.EXITS_PLACING
        ):
            group.drive_pending = True
        return io

    async def _after(self, group: _Group, io: list[_IoAction]) -> None:
        await self._exec(group, io)
        if group.drive_pending and not group.driving:
            group.drive_pending = False
            await self._drive(group)

    async def _exec(self, group: _Group, io: list[_IoAction]) -> None:
        queue = deque(io)
        while queue:
            act = queue.popleft()
            if isinstance(act, CancelLeg):
                queue.extend(await self._do_cancel(group, act.leg_index))
            else:
                queue.extend(await self._do_get(group, act.leg_index))

    async def _do_cancel(self, group: _Group, index: int) -> list[_IoAction]:
        async with group.lock:
            rec = group.record
            cid = rec.legs[index].client_order_id
            if cid is None:
                return []
            if not cancel_still_due(rec, index):  # stale: another task changed the group
                return self._commit(
                    group, withdraw_cancel(rec, index, self._now(), closed=group.closed)
                )
        try:
            outcome = await self._venue.cancel_leg(rec.target, cid)
        except Exception:
            logger.warning("cancel_leg failed for %s; leg stays unresolved", cid, exc_info=True)
            outcome = CancelOutcome.UNKNOWN
        async with group.lock:
            trans = apply_cancel_outcome(
                group.record, index, outcome, self._now(), closed=group.closed
            )
            return self._commit(group, trans)

    async def _do_get(self, group: _Group, index: int) -> list[_IoAction]:
        rec = group.record
        cid, tag = rec.legs[index].client_order_id, rec.legs[index].link_tag
        by_tag = cid is None
        # One lookup per leg at a time; a leg whose placement reply is pending has no id yet.
        if index in group.getting or (by_tag and (tag is None or index in group.inflight)):
            return []
        group.getting.add(index)
        try:
            snapshot = await self._safe_get(
                rec.target, client_order_id=cid, link_tag=tag if by_tag else None
            )
        finally:
            group.getting.discard(index)
        if snapshot is None and by_tag:  # "not found by tag" is no information
            return []
        # A retry of get_leg belongs to the next tick(), never to this loop.
        follow = await self._apply_snapshot(group, index, snapshot)
        return [act for act in follow if isinstance(act, CancelLeg)]

    async def _apply_snapshot(
        self, group: _Group, index: int, snapshot: LegSnapshot | None
    ) -> list[_IoAction]:
        async with group.lock:
            trans = apply_snapshot(group.record, index, snapshot, self._now(), closed=group.closed)
            return self._commit(group, trans)

    async def _safe_get(
        self, target: str, *, client_order_id: str | None = None, link_tag: LinkTag | None = None
    ) -> LegSnapshot | None:
        try:
            snapshot = await self._venue.get_leg(
                target, client_order_id=client_order_id, link_tag=link_tag
            )
        except Exception:
            logger.warning("get_leg failed for %s", client_order_id or link_tag, exc_info=True)
            return None
        if snapshot is not None and not self._valid_snapshot(
            snapshot, f"get_leg for {client_order_id or link_tag}"
        ):
            return None
        return snapshot

    @staticmethod
    def _valid_snapshot(snapshot: LegSnapshot, source: str) -> bool:
        """A negative fill is venue garbage: reject it as "no information", never as "gone"."""
        if snapshot.filled < 0:
            logger.warning(
                "%s reported a negative fill (%s); snapshot rejected", source, snapshot.filled
            )
            return False
        return True

    # ------------------------------------------------------------------ intake buffer

    def _group_for(self, client_order_id: str) -> _Group | None:
        group_id = self._by_cid.get(client_order_id)
        return None if group_id is None else self._groups.get(group_id)

    def _buffer_add(self, client_order_id: str, item: OrderState | LegFill) -> None:
        if len(self._buffer) >= self._config.unmatched_buffer_max:
            dropped = self._buffer.popleft()
            logger.warning("unmatched buffer full: dropped report for %s", dropped.client_order_id)
        self._buffer.append(_Buffered(self._now(), client_order_id, item))

    def _take_buffered(self, client_order_id: str) -> list[OrderState | LegFill]:
        taken = [b for b in self._buffer if b.client_order_id == client_order_id]
        if not taken:
            return []
        self._buffer = deque(b for b in self._buffer if b.client_order_id != client_order_id)
        items: list[OrderState | LegFill] = []
        filled = Decimal(0)
        for entry in taken:
            if isinstance(entry.item, LegFill):
                if not self._intake.accept(entry.item, filled):
                    continue
                filled = entry.item.cumulative_filled
            items.append(entry.item)
        return items

    def _expire_buffer(self, now: float) -> None:
        keep: deque[_Buffered] = deque()
        for entry in self._buffer:
            if now - entry.at > self._config.grace_period_s:
                logger.warning("unmatched report for %s expired", entry.client_order_id)
            else:
                keep.append(entry)
        self._buffer = keep

    def _purge(self, group: _Group) -> None:
        self._groups.pop(group.record.group_id, None)
        for leg in group.record.legs:
            if leg.client_order_id is not None:
                self._by_cid.pop(leg.client_order_id, None)

    # ------------------------------------------------------------------ recovery

    def _load(self, record: GroupRecord, now: float) -> _Group:
        """Adopt a stored record; every leg that reached (or may have reached) the venue is
        unresolved until the venue answers, which defers any cancel until all are reconciled."""
        legs = tuple(
            replace(leg, unresolved_since=now, retry_at=None, retry_delay_s=None)
            if leg.status is not LegStatus.NOT_PLACED
            else leg
            for leg in record.legs
        )
        group = _Group(replace(record, legs=legs))
        self._groups[record.group_id] = group
        for leg in legs:
            if leg.client_order_id is not None:
                self._by_cid[leg.client_order_id] = record.group_id
        return group

    async def _reconcile_store_to_venue(self, group: _Group) -> None:
        for leg in list(group.record.legs):
            target = group.record.target
            if leg.client_order_id is not None:
                snapshot = await self._safe_get(target, client_order_id=leg.client_order_id)
            elif leg.link_tag is not None and leg.status in _PLACEABLE_STATUSES:
                snapshot = await self._safe_get(target, link_tag=leg.link_tag)
                if snapshot is None:
                    continue  # never assumed unplaced, never re-submitted: grace will surface it
            else:
                continue
            await self._exec(group, await self._apply_snapshot(group, leg.leg_index, snapshot))

    async def _reconcile_venue_to_store(self, targets: Sequence[str]) -> set[GroupId]:
        orphans: set[GroupId] = set()
        for target in targets:
            for snap in await self._list_open(target):
                decoded = self._decode(snap.link_tag)
                if decoded is None:
                    continue
                group_id, index = decoded
                self._next_id = max(self._next_id, group_id + 1)
                if not self._valid_snapshot(snap, f"list_open_legs for {target}"):
                    continue  # no information: neither an orphan nor a match
                group = self._groups.get(group_id)
                if group is None:
                    orphans.add(group_id)
                    await self._handle_orphan(target, group_id, index, snap)
                else:
                    await self._match_leg(group, index, snap)
        return orphans

    async def _list_open(self, target: str) -> Sequence[LegSnapshot]:
        try:
            return await self._venue.list_open_legs(target)
        except Exception:
            logger.warning("list_open_legs failed for %s", target, exc_info=True)
            return []

    def _decode(self, tag: LinkTag | None) -> tuple[GroupId, int] | None:
        if tag is None:
            return None
        try:
            return self._codec.decode(tag)
        except Exception:
            return None

    async def _handle_orphan(
        self, target: str, group_id: GroupId, index: int, snap: LegSnapshot
    ) -> None:
        self._emit(
            LinkedGroupEvent(
                kind=LinkedEventKind.ORPHAN_FOUND,
                group_id=str(group_id),
                link_kind=None,
                target=target,
                state=None,
                timestamp=self._now(),
                leg_index=index,
                client_order_ids=(snap.client_order_id,),
                filled=(snap.filled,),
            )
        )
        if self._config.cancel_orphans:
            try:
                await self._venue.cancel_leg(target, snap.client_order_id)
            except Exception:
                logger.warning("could not cancel orphan %s", snap.client_order_id, exc_info=True)

    async def _match_leg(self, group: _Group, index: int, snap: LegSnapshot) -> None:
        rec = group.record
        leg = rec.legs[index] if index < len(rec.legs) else None
        if leg is not None and leg.client_order_id == snap.client_order_id:
            return
        if leg is not None and leg.client_order_id is None and leg.status in _PLACEABLE_STATUSES:
            await self._exec(group, await self._apply_snapshot(group, index, snap))
            return
        async with group.lock:
            trans = mark_link_broken(
                rec,
                index,
                f"venue order {snap.client_order_id} does not match the stored leg {index}",
                self._now(),
            )
            io = self._commit(group, trans)
        await self._exec(group, io)

    async def _resume(self, group: _Group) -> None:
        async with group.lock:
            rec = group.record
            io = self._commit(group, resume(rec, self._now()))
            if (
                group.record.state in (GroupState.PLACING, GroupState.EXITS_PLACING)
                and can_place(group.record)
                and len(group.record.legs) < leg_count(group.record)
            ):
                group.drive_pending = True
        await self._after(group, io)

    def _seed_counter(self) -> None:
        stored = [gid + 1 for gid in self._groups]
        self._next_id = max([self._next_id, self._checked_lower_bound(), *stored])

    # ------------------------------------------------------------------ events

    def _now(self) -> float:
        return self._clock.time()

    def _event(self, kind: LinkedEventKind, record: GroupRecord, detail: str) -> LinkedGroupEvent:
        return LinkedGroupEvent(
            kind=kind,
            group_id=str(record.group_id),
            link_kind=record.spec.kind,
            target=record.target,
            state=record.state,
            timestamp=self._now(),
            client_order_ids=tuple(leg.client_order_id for leg in record.legs),
            filled=tuple(leg.filled for leg in record.legs),
            detail=detail,
        )

    def _emit(self, event: LinkedGroupEvent) -> None:
        if event.kind in _WARNED_KINDS:
            logger.warning(
                "linked group %s %s %s: %s",
                event.group_id,
                event.kind.value,
                event.reason.value if event.reason else "",
                event.detail,
            )
        if self._bus is None:
            return
        try:
            self._bus.emit(LINKED_GROUP_EVENT, event)
        except Exception:
            logger.exception("linked-group event emitter failed")

    def _require(self, group_id: str) -> _Group:
        try:
            group = self._groups.get(int(group_id))
        except ValueError:
            group = None
        if group is None:
            raise LinkedGroupNotFoundError(group_id)
        return group


__all__ = ["EmulatedLinkedOrderManager"]
