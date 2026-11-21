"""Injected `GroupIdAllocator`: the group id comes solely from it (#98)."""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

import pytest

from strategy_framework.linked_orders import (
    GroupIdAllocator,
    GroupIdPersistenceError,
    GroupIdSpaceExhaustedError,
    GroupInvariantError,
    LinkIdCodecError,
)
from strategy_framework.linked_orders.config import LinkedOrderManagerConfig
from strategy_framework.linked_orders.events import LinkedEventKind as K
from strategy_framework.linked_orders.manager import EmulatedLinkedOrderManager
from strategy_framework.testing.fake_linked_venue import ManualClock, StringLinkIdCodec
from tests.unit.linked_orders.builders import oco_spec
from tests.unit.linked_orders.manager_helpers import TARGET, SpyStore, events
from tests.unit.linked_orders.test_group_id_never_repeats import HwmStore

if TYPE_CHECKING:
    from strategy_framework.linked_orders.types import GroupId
    from strategy_framework.testing.fake_linked_venue import FakeEmulationVenue, RecordingEmitter


class FakeAllocator:
    """Lock + counter; an optional injected failure."""

    def __init__(self, start: int = 1, fail: Exception | None = None) -> None:
        self._next = start
        self._lock = asyncio.Lock()
        self.fail = fail
        self.calls = 0

    async def reserve_group_id(self) -> GroupId:
        async with self._lock:
            self.calls += 1
            await asyncio.sleep(0)  # force interleaving between managers
            if self.fail is not None:
                raise self.fail
            value = self._next
            self._next += 1
            return value


class ScriptedAllocator:
    """Returns the scripted values in order (possibly invalid ones)."""

    def __init__(self, values: list[object]) -> None:
        self._values = iter(values)

    async def reserve_group_id(self) -> GroupId:
        return next(self._values)  # type: ignore[return-value]


class BoundedCodec(StringLinkIdCodec):
    max_group_id = 100


class RejectingCodec(StringLinkIdCodec):
    def encode(self, group_id: int, leg_index: int) -> str:
        msg = "cannot encode"
        raise ValueError(msg)


class SpyHwmStore(HwmStore):
    def __init__(self) -> None:
        super().__init__()
        self.hwm = 10**6
        self.loads = 0

    def load_group_id_hwm(self) -> int | None:
        self.loads += 1
        return super().load_group_id_hwm()


def _mgr(
    venue: FakeEmulationVenue,
    codec: StringLinkIdCodec,
    allocator: GroupIdAllocator | None,
    store: SpyStore | None = None,
    config: LinkedOrderManagerConfig | None = None,
    clock: ManualClock | None = None,
    bus: RecordingEmitter | None = None,
) -> EmulatedLinkedOrderManager:
    return EmulatedLinkedOrderManager(
        venue,
        codec,
        config or LinkedOrderManagerConfig(enabled=True),
        store=store or SpyStore(),
        clock=clock or ManualClock(),
        bus=bus,
        allocator=allocator,
    )


def _gids(venue: FakeEmulationVenue) -> list[int]:
    tags = [str(c[3]) for c in venue.calls("place_leg")]
    return [int(re.match(r"hbl-(\d+)-", t).group(1)) for t in tags]  # type: ignore[union-attr]


def test_fake_satisfies_protocol() -> None:
    assert isinstance(FakeAllocator(), GroupIdAllocator)


async def test_two_managers_sharing_an_allocator_never_collide(
    venue: FakeEmulationVenue, codec: StringLinkIdCodec
) -> None:
    allocator = FakeAllocator()
    config = LinkedOrderManagerConfig(enabled=True, group_id_seed=500)  # identical seed and floor
    clock = ManualClock()  # same second
    a = _mgr(venue, codec, allocator, SpyStore(), config, clock)
    b = _mgr(venue, codec, allocator, SpyStore(), config, clock)
    await a.recover([])
    await b.recover([])
    handles = await asyncio.gather(
        *[(a if i % 2 else b).place_oco(TARGET, oco_spec()) for i in range(40)]
    )
    ids = [h.group_id for h in handles]
    assert len(set(ids)) == 40
    assert sorted(int(i) for i in ids) == list(range(1, 41))  # seed and floor ignored
    assert len(set(_gids(venue))) == 40
    assert set(_gids(venue)) == {int(i) for i in ids}
    assert sorted(_gids(venue)) == sorted(int(i) for i in ids for _ in range(2))  # 2 legs per OCO


async def test_recover_with_foreign_legs_does_not_move_the_id_source(
    venue: FakeEmulationVenue, codec: StringLinkIdCodec, emitter: RecordingEmitter
) -> None:
    leg = oco_spec().legs[0]
    await venue.place_leg(TARGET, leg, link_tag="hbl-500-0")
    await venue.place_leg(TARGET, leg, link_tag="hbl-900-1")
    manager = _mgr(venue, codec, FakeAllocator(), bus=emitter)
    await manager.recover([TARGET])
    assert sorted(e.group_id for e in events(emitter, K.ORPHAN_FOUND)) == ["500", "900"]
    assert venue.calls("cancel_leg") == []
    handle = await manager.place_oco(TARGET, oco_spec())
    assert handle.group_id == "1"


async def test_allocator_failure_fails_closed(
    venue: FakeEmulationVenue, codec: StringLinkIdCodec
) -> None:
    cause = OSError("database is locked")
    store = SpyStore()
    manager = _mgr(venue, codec, FakeAllocator(fail=cause), store)
    await manager.recover([])
    with pytest.raises(GroupIdPersistenceError) as info:
        await manager.place_oco(TARGET, oco_spec())
    assert info.value.__cause__ is cause
    assert info.value.group_id is None
    assert venue.calls("place_leg") == []
    assert store.saves == []
    assert not manager.has_pending_orders


async def test_negative_then_non_int_ids_fail_closed(
    venue: FakeEmulationVenue, codec: StringLinkIdCodec
) -> None:
    store = SpyStore()
    allocator = ScriptedAllocator([-1, "7", True])
    manager = _mgr(venue, codec, allocator, store)
    await manager.recover([])
    for expected in (ValueError, TypeError, TypeError):
        with pytest.raises(GroupIdPersistenceError) as info:
            await manager.place_oco(TARGET, oco_spec())
        assert info.value.group_id is None
        assert isinstance(info.value.__cause__, expected)
    assert store.saves == []
    assert venue.calls("place_leg") == []
    assert not manager.has_pending_orders


async def test_duplicate_id_is_an_invariant_error_and_keeps_the_original(
    venue: FakeEmulationVenue, codec: StringLinkIdCodec
) -> None:
    store = SpyStore()
    manager = _mgr(venue, codec, ScriptedAllocator([5, 5]), store)
    await manager.recover([])
    first = await manager.place_oco(TARGET, oco_spec())
    saves, legs = len(store.saves), len(venue.calls("place_leg"))
    with pytest.raises(GroupInvariantError):
        await manager.place_oco(TARGET, oco_spec())
    assert len(store.saves) == saves
    assert len(venue.calls("place_leg")) == legs
    assert manager.get_handle(first.group_id).group_id == first.group_id
    assert manager.has_pending_orders


async def test_codec_rejection_under_an_allocator_persists_nothing(
    venue: FakeEmulationVenue,
) -> None:
    store = SpyStore()
    manager = _mgr(venue, RejectingCodec(), FakeAllocator(), store)
    await manager.recover([])
    with pytest.raises(LinkIdCodecError):
        await manager.place_oco(TARGET, oco_spec())
    assert store.saves == []
    assert venue.calls("place_leg") == []
    assert not manager.has_pending_orders


def test_construction_with_allocator_ignores_seed_above_the_bound(
    venue: FakeEmulationVenue,
) -> None:
    config = LinkedOrderManagerConfig(enabled=True, group_id_seed=10**6)
    manager = _mgr(venue, BoundedCodec(), FakeAllocator(), SpyHwmStore(), config)
    assert not manager.has_pending_orders


async def test_reserved_id_over_the_codec_bound_is_rejected(venue: FakeEmulationVenue) -> None:
    store = SpyStore()
    manager = _mgr(venue, BoundedCodec(), FakeAllocator(start=101), store)
    await manager.recover([])
    with pytest.raises(GroupIdSpaceExhaustedError):
        await manager.place_oco(TARGET, oco_spec())
    assert venue.calls("place_leg") == []
    assert store.saves == []


async def test_reserved_id_at_the_bound_is_accepted(venue: FakeEmulationVenue) -> None:
    manager = _mgr(venue, BoundedCodec(), FakeAllocator(start=100))
    await manager.recover([])
    handle = await manager.place_oco(TARGET, oco_spec())
    assert handle.group_id == "100"
    assert set(_gids(venue)) == {100}


async def test_allocator_id_held_by_a_live_orphan_is_rejected(
    venue: FakeEmulationVenue, codec: StringLinkIdCodec
) -> None:
    await venue.place_leg(TARGET, oco_spec().legs[0], link_tag="hbl-7-0")
    store = SpyStore()
    manager = _mgr(venue, codec, ScriptedAllocator([7, 8]), store)
    await manager.recover([TARGET])
    legs = len(venue.calls("place_leg"))
    with pytest.raises(GroupInvariantError):
        await manager.place_oco(TARGET, oco_spec())
    assert len(venue.calls("place_leg")) == legs
    assert store.saves == []
    assert not manager.has_pending_orders
    handle = await manager.place_oco(TARGET, oco_spec())
    assert handle.group_id == "8"


async def test_hwm_store_and_seed_are_not_consulted(
    venue: FakeEmulationVenue, codec: StringLinkIdCodec
) -> None:
    store = SpyHwmStore()
    config = LinkedOrderManagerConfig(enabled=True, group_id_seed=5000)
    manager = _mgr(venue, codec, FakeAllocator(start=7), store, config)
    await manager.recover([])
    handle = await manager.place_oco(TARGET, oco_spec())
    assert handle.group_id == "7"
    assert store.loads == 0
    assert store.hwm == 10**6
    assert not [e for e in store.log if e[0] == "save_hwm"]
