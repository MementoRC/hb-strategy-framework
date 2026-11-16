"""Bounded codecs: the group-id space is checked, never clamped or wrapped (#90)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from strategy_framework.linked_orders import (
    BoundedLinkIdCodec,
    GroupIdSpaceExhaustedError,
    LinkedOrderError,
    LinkedOrderIdCodec,
    LinkIdCodecError,
)
from strategy_framework.linked_orders.config import LinkedOrderManagerConfig
from strategy_framework.linked_orders.manager import _GROUP_ID_EPOCH, EmulatedLinkedOrderManager
from strategy_framework.testing.fake_linked_venue import ManualClock, StringLinkIdCodec
from tests.unit.linked_orders.builders import oco_spec
from tests.unit.linked_orders.manager_helpers import TARGET, SpyStore
from tests.unit.linked_orders.test_group_id_never_repeats import HwmStore

if TYPE_CHECKING:
    from strategy_framework.linked_orders.types import GroupId, LinkTag
    from strategy_framework.testing.fake_linked_venue import FakeEmulationVenue

INT32_MAX = 2**31 - 1
NOV_16_2026 = _GROUP_ID_EPOCH + 319 * 86_400  # default factor 100 floor = 2.756e9 > int32
DEFAULT = LinkedOrderManagerConfig(enabled=True)
FACTOR_1 = LinkedOrderManagerConfig(enabled=True, group_id_time_factor=1)
NO_FLOOR = LinkedOrderManagerConfig(enabled=True, group_id_time_factor=0)


class BoundedCodec(StringLinkIdCodec):
    max_group_id = INT32_MAX


class RejectingCodec(StringLinkIdCodec):
    """Unbounded; encodes anything but cannot round-trip ids at or above `limit`."""

    def __init__(self, limit: int) -> None:
        self.limit = limit

    def decode(self, tag: LinkTag) -> tuple[GroupId, int] | None:
        decoded = super().decode(tag)
        if decoded is None or decoded[0] >= self.limit:
            return None
        return decoded


def _mgr(
    venue: FakeEmulationVenue,
    codec: LinkedOrderIdCodec,
    clock: ManualClock,
    store: SpyStore,
    config: LinkedOrderManagerConfig,
) -> EmulatedLinkedOrderManager:
    return EmulatedLinkedOrderManager(venue, codec, config, store=store, clock=clock)


def _gids(venue: FakeEmulationVenue) -> list[int]:
    tags = [str(c[3]) for c in venue.calls("place_leg")]
    return [int(re.match(r"hbl-(\d+)-", t).group(1)) for t in tags]  # type: ignore[union-attr]


def test_isinstance_detection() -> None:
    assert isinstance(BoundedCodec(), BoundedLinkIdCodec)
    assert not isinstance(StringLinkIdCodec(), BoundedLinkIdCodec)


def test_default_factor_overflows_int32_at_construction(venue: FakeEmulationVenue) -> None:
    clock = ManualClock(NOV_16_2026)
    with pytest.raises(GroupIdSpaceExhaustedError) as info:
        _mgr(venue, BoundedCodec(), clock, SpyStore(), DEFAULT)
    assert isinstance(info.value, LinkedOrderError)
    message = str(info.value)
    assert str(INT32_MAX) in message
    assert "time floor" in message
    assert "group_id_time_factor" in message
    assert info.value.max_group_id == INT32_MAX
    assert info.value.lower_bound > INT32_MAX


async def test_factor_one_fits_int32(venue: FakeEmulationVenue) -> None:
    clock = ManualClock(NOV_16_2026)
    manager = _mgr(venue, BoundedCodec(), clock, HwmStore(venue.call_log), FACTOR_1)
    await manager.place_oco(TARGET, oco_spec())
    gids = _gids(venue)
    assert gids
    assert all(0 < g <= INT32_MAX for g in gids)


async def test_placement_over_bound_raises_and_persists_nothing(venue: FakeEmulationVenue) -> None:
    clock = ManualClock()
    store = HwmStore(venue.call_log)
    manager = _mgr(venue, BoundedCodec(), clock, store, NO_FLOOR)
    store.hwm = INT32_MAX  # the next safe id is INT32_MAX + 1
    counter = manager._next_id  # noqa: SLF001
    with pytest.raises(GroupIdSpaceExhaustedError, match="HWM"):
        await manager.place_oco(TARGET, oco_spec())
    assert store.hwm == INT32_MAX
    assert ("save_hwm", INT32_MAX + 1) not in store.log
    assert manager._next_id == counter  # noqa: SLF001
    assert venue.calls("place_leg") == []
    assert store.load_all() == []


async def test_counter_at_max_raises(venue: FakeEmulationVenue) -> None:
    store = HwmStore(venue.call_log)
    manager = _mgr(venue, BoundedCodec(), ManualClock(), store, NO_FLOOR)
    manager._next_id = INT32_MAX  # noqa: SLF001
    await manager.place_oco(TARGET, oco_spec())  # INT32_MAX itself still fits
    assert _gids(venue)[-1] == INT32_MAX
    placed = len(venue.calls("place_leg"))
    with pytest.raises(GroupIdSpaceExhaustedError, match="counter"):
        await manager.place_oco(TARGET, oco_spec())
    assert len(venue.calls("place_leg")) == placed
    assert store.hwm == INT32_MAX


def test_seed_over_bound_fails_construction(venue: FakeEmulationVenue) -> None:
    config = LinkedOrderManagerConfig(
        enabled=True, group_id_time_factor=0, group_id_seed=INT32_MAX + 1
    )
    with pytest.raises(GroupIdSpaceExhaustedError, match="seed"):
        _mgr(venue, BoundedCodec(), ManualClock(), SpyStore(), config)


async def test_recover_raises_when_bound_exceeds_max(venue: FakeEmulationVenue) -> None:
    clock = ManualClock()
    store = HwmStore(venue.call_log)
    manager = _mgr(venue, BoundedCodec(), clock, store, NO_FLOOR)
    store.hwm = INT32_MAX
    with pytest.raises(GroupIdSpaceExhaustedError):
        await manager.recover([])


async def test_round_trip_rejection_does_not_persist_hwm(venue: FakeEmulationVenue) -> None:
    store = HwmStore(venue.call_log)
    config = LinkedOrderManagerConfig(enabled=True, group_id_time_factor=0, group_id_seed=1000)
    manager = _mgr(venue, RejectingCodec(limit=1000), ManualClock(), store, config)
    counter = manager._next_id  # noqa: SLF001
    with pytest.raises(LinkIdCodecError):
        await manager.place_oco(TARGET, oco_spec())
    assert store.hwm is None
    assert not [e for e in venue.call_log if e[0] == "save_hwm"]
    assert manager._next_id == counter  # noqa: SLF001
    assert venue.calls("place_leg") == []


async def test_unbounded_codec_keeps_old_behaviour(venue: FakeEmulationVenue) -> None:
    clock = ManualClock(NOV_16_2026)
    manager = _mgr(venue, StringLinkIdCodec(), clock, SpyStore(venue.call_log), DEFAULT)
    await manager.place_oco(TARGET, oco_spec())
    assert _gids(venue)[-1] > INT32_MAX
