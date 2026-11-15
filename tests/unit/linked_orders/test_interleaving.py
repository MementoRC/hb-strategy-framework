"""Tests K: seeded randomized interleavings, asserting I1-I8 after every step.

Each schedule places one group and then randomly releases delayed venue replies, delivers
reordered and duplicated updates and fills, injects NOT_FOUND / UNKNOWN / ALREADY_FILLED
outcomes and empty lookups, advances the clock past the grace period and requests cancels.
The failing seed is printed (and is in the assertion message) so it can be replayed.
"""

from __future__ import annotations

import asyncio
import random
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from data_type_primitives import OrderState

from strategy_framework.linked_orders.config import LinkedOrderManagerConfig
from strategy_framework.linked_orders.errors import LinkedGroupNotFoundError
from strategy_framework.linked_orders.events import LinkedEventKind
from strategy_framework.linked_orders.manager import EmulatedLinkedOrderManager
from strategy_framework.linked_orders.state import any_unresolved, is_terminal, is_unresolved
from strategy_framework.linked_orders.types import CancelOutcome, GroupState, LegFill
from strategy_framework.testing.fake_linked_venue import (
    FakeEmulationVenue,
    ManualClock,
    RecordingEmitter,
    StringLinkIdCodec,
)
from tests.unit.linked_orders.builders import bracket_spec, oco_spec
from tests.unit.linked_orders.invariants import (
    monotonic_violations,
    sibling_fill_violations,
    violations,
)
from tests.unit.linked_orders.manager_helpers import TARGET, SpyStore, spawn, spin

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from data_type_primitives import LinkedOrderSpec

    from strategy_framework.linked_orders.manager import _Group
    from strategy_framework.linked_orders.state import CancelLeg, GetLeg, Transition
    from strategy_framework.linked_orders.types import GroupRecord

SEEDS_PER_CHUNK = 100
CHUNKS = 5  # 500 seeds per shape
STEPS = 40
METHODS = ("place_leg", "cancel_leg", "get_leg")
_PLACING = {GroupState.PLACING, GroupState.EXITS_PLACING, GroupState.DEGRADED}
_STATES = [
    OrderState.OPEN,
    OrderState.PARTIALLY_FILLED,
    OrderState.FILLED,
    OrderState.CANCELED,
    OrderState.FAILED,
    OrderState.UNKNOWN,
]
SHAPES: dict[str, Callable[[], LinkedOrderSpec]] = {
    "oco2": lambda: oco_spec(2),
    "oco3": lambda: oco_spec(3),
    "bracket_tp": lambda: bracket_spec(stop_loss=False),
    "bracket_sl": lambda: bracket_spec(take_profit=False),
    "bracket_tp_sl": bracket_spec,
}


class Checker:
    """Asserts I1-I8 against the venue call log, the store writes, and the live records."""

    def __init__(
        self,
        manager: EmulatedLinkedOrderManager,
        venue: FakeEmulationVenue,
        store: SpyStore,
        emitter: RecordingEmitter,
    ) -> None:
        self.manager, self.venue, self.store, self.emitter = manager, venue, store, emitter
        self.cursor = 0
        self.placed_tags: set[str] = set()
        self.prev: dict[int, GroupRecord] = {}
        self.transition_problems: list[str] = []
        commit = manager._commit  # noqa: SLF001

        def spy(group: _Group, trans: Transition) -> list[CancelLeg | GetLeg]:
            bad = violations(group.record, trans, closed=group.closed)
            self.transition_problems += [f"{b} [{trans.record.state.name}]" for b in bad]
            return commit(group, trans)

        manager._commit = spy  # type: ignore[method-assign]  # noqa: SLF001

    def check(self) -> None:
        problems: list[str] = list(self.transition_problems)
        log = self.venue.call_log
        cid_group = self._cid_groups()
        for pos in range(self.cursor, len(log)):
            entry = log[pos]
            if entry[0] == "place_leg":
                problems += self._place(pos, entry)
            elif entry[0] == "cancel_leg":
                problems += self._cancel(pos, entry, cid_group)
        self.cursor = len(log)
        problems += self._groups()
        problems += self._degraded_events()
        assert not problems, problems

    def _cid_groups(self) -> dict[str, int]:
        mapping: dict[str, int] = {}
        for rec in [*self.store.saves, *(g.record for g in self.manager._groups.values())]:  # noqa: SLF001
            for leg in rec.legs:
                if leg.client_order_id is not None:
                    mapping[leg.client_order_id] = rec.group_id
        return mapping

    def _last_save(self, pos: int, group_id: int, tag: str | None = None) -> GroupRecord | None:
        for entry in reversed(self.venue.call_log[:pos]):
            if entry[0] != "save" or entry[1] != group_id:
                continue
            if tag is None or (tag, "PENDING_CREATE") in entry[2]:
                return self.store.saves[entry[3]]
        return None

    def _place(self, pos: int, entry: tuple[object, ...]) -> list[str]:
        tag = str(entry[3])
        out = []
        if tag in self.placed_tags:
            out.append(f"{tag} placed twice")
        self.placed_tags.add(tag)
        rec = self._last_save(pos, int(tag.split("-")[1]), tag)
        if rec is None:
            return [*out, f"I7: place_leg {tag} without a write-ahead save"]
        if rec.winner_leg_index is not None or rec.cancel_cause is not None:
            out.append(f"I4: place_leg {tag} after trigger/cancel ({rec.state.name})")
        if rec.state not in _PLACING:
            out.append(f"I4: place_leg {tag} while {rec.state.name}")
        return out

    def _cancel(self, pos: int, entry: tuple[object, ...], cid_group: dict[str, int]) -> list[str]:
        cid = str(entry[2])
        rec = self._last_save(pos, cid_group[cid])
        if rec is None:
            return [f"I7: cancel {cid} without any save"]
        out = []
        index = next(leg.leg_index for leg in rec.legs if leg.client_order_id == cid)
        if rec.cancel_cause != "user" and any_unresolved(rec):
            out.append(f"I1: fill-triggered/rollback cancel of {cid} while a leg is unresolved")
        if is_unresolved(rec.legs[index]):
            out.append(f"I1: cancel of unresolved leg {cid}")
        return out

    def _groups(self) -> list[str]:
        out: list[str] = []
        stored = {rec.group_id: rec for rec in self.store.load_all()}
        for gid, group in self.manager._groups.items():  # noqa: SLF001
            rec = group.record
            out += sibling_fill_violations(rec)
            if gid in self.prev:
                out += monotonic_violations(self.prev[gid], rec)
            self.prev[gid] = rec
            if group.closed:
                if not all(is_terminal(leg) for leg in rec.legs) or gid in stored:
                    out.append(f"I2: group {gid} closed but not terminal / still stored")
            elif stored.get(gid) != rec:
                out.append(f"I7: group {gid} live record differs from the stored record")
        return out

    def _degraded_events(self) -> list[str]:
        seen: set[tuple[str, object]] = set()
        out = []
        for payload in self.emitter.payloads():
            if getattr(payload, "kind", None) is LinkedEventKind.DEGRADED:
                key = (payload.group_id, payload.reason)  # type: ignore[attr-defined]
                if key in seen:
                    out.append(f"I3: duplicate DEGRADED event {key}")
                seen.add(key)
        return out


class Schedule:
    """One seeded random schedule against one group."""

    def __init__(self, seed: int, make_spec: Callable[[], LinkedOrderSpec]) -> None:
        self.seed = seed
        self.rng = random.Random(seed)
        self.make_spec = make_spec
        self.venue = FakeEmulationVenue()
        self.clock = ManualClock()
        self.emitter = RecordingEmitter()
        self.store = SpyStore(self.venue.call_log)
        self.manager = EmulatedLinkedOrderManager(
            self.venue,
            StringLinkIdCodec(),
            LinkedOrderManagerConfig(enabled=True, grace_period_s=30.0, unmatched_buffer_max=8),
            store=self.store,
            clock=self.clock,
            bus=self.emitter,
        )
        self.checker = Checker(self.manager, self.venue, self.store, self.emitter)
        self.tasks: list[asyncio.Task[object]] = []
        self.fills: list[LegFill] = []

    def go(self, coro: Coroutine[object, object, object]) -> None:
        self.tasks.append(spawn(coro))

    async def run(self) -> None:
        rng, venue = self.rng, self.venue
        venue.script_place(
            *[rng.choices(["ok", "unknown", "reject"], [8, 2, 1])[0] for _ in range(4)]
        )
        for method in METHODS:
            if rng.random() < 0.5:
                venue.hold(method)
        spec = self.make_spec()
        place = self.manager.place_oco if spec.kind.value == "oco" else self.manager.place_bracket
        self.go(place(TARGET, spec))
        await spin(3)
        self.checker.check()
        for _ in range(STEPS):
            self.step()
            await spin(3)
            self.checker.check()
        await self.drain()

    def step(self) -> None:
        rng, venue = self.rng, self.venue
        op = rng.choices(
            ["release", "update", "fill", "deliver", "tick", "late", "script", "cancel"],
            [5, 4, 4, 5, 3, 2, 3, 1],
        )[0]
        cids = list(venue.orders)
        if op == "release":
            venue.release(rng.choice(METHODS))
        elif op == "update" and cids:
            update = venue.update(rng.choice(cids), rng.choice(_STATES))
            for _ in range(rng.choice([1, 1, 2])):
                self.go(self.manager.on_order_update(update))
        elif op == "fill" and cids:
            cid = rng.choice(cids)
            amount = venue.orders[cid].amount
            cumulative = amount * Decimal(rng.choice(["0.25", "0.5", "1"]))
            fill_id = rng.choice([None, f"f{rng.randrange(3)}"])
            self.fills.append(venue.fill(cid, cumulative, fill_id=fill_id))
        elif op == "deliver" and self.fills:
            fill = rng.choice(self.fills)  # reordered; stays in the pool, so it can repeat
            self.go(self.manager.on_fill(fill))
        elif op == "tick":
            self.go(self.manager.tick())
        elif op == "late":
            self.clock.advance(rng.choice([1, 5, 31, 301]))
            self.go(self.manager.tick())
        elif op == "script":
            if rng.random() < 0.5:
                venue.script_cancel(rng.choice(list(CancelOutcome)))
            else:
                venue.script_get(None)
        elif op == "cancel":
            self.request_cancel()

    def request_cancel(self) -> None:
        try:
            handle = self.manager.get_handle("1")
        except LinkedGroupNotFoundError:
            return
        self.go(self.manager.cancel_linked(handle))

    async def drain(self) -> None:
        for _ in range(30):
            for method in METHODS:
                self.venue.release_all(method)
            await spin(3)
            if all(task.done() for task in self.tasks):
                break
        self.checker.check()
        for _ in range(2):
            self.clock.advance(31)
            await self.manager.tick()
            self.checker.check()
        results = await asyncio.gather(*self.tasks, return_exceptions=True)
        errors = [r for r in results if isinstance(r, BaseException)]
        assert not errors, errors


@pytest.mark.parametrize("chunk", range(CHUNKS))
@pytest.mark.parametrize("shape", list(SHAPES))
async def test_random_interleavings_hold_invariants(shape: str, chunk: int) -> None:
    final_states: set[GroupState] = set()
    for seed in range(chunk * SEEDS_PER_CHUNK, (chunk + 1) * SEEDS_PER_CHUNK):
        schedule = Schedule(seed, SHAPES[shape])
        try:
            await schedule.run()
        except BaseException:
            print(f"FAILING SEED: shape={shape} seed={seed}")  # noqa: T201
            raise
        final_states.add(schedule.checker.prev[1].state)  # the tombstone may be purged by now
    # the schedules must actually reach different outcomes, not idle in one state
    assert len(final_states) >= 3, final_states
