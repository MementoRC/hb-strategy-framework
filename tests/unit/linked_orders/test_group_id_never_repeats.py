"""Group ids never repeat on an account: persisted HWM plus a time-derived floor."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import pytest

from strategy_framework.linked_orders import (
    GroupIdHighWaterStore,
    GroupIdPersistenceError,
    LinkedGroupStore,
    LinkedOrderError,
    RecoveryRequiredError,
)
from strategy_framework.linked_orders.config import LinkedOrderManagerConfig
from strategy_framework.linked_orders.manager import _GROUP_ID_EPOCH
from strategy_framework.testing.fake_linked_venue import ManualClock
from tests.unit.linked_orders.builders import oco_spec
from tests.unit.linked_orders.manager_helpers import TARGET, SpyStore, make_manager

if TYPE_CHECKING:
    from strategy_framework.linked_orders.manager import EmulatedLinkedOrderManager
    from strategy_framework.testing.fake_linked_venue import (
        FakeEmulationVenue,
        StringLinkIdCodec,
    )

NO_FLOOR = LinkedOrderManagerConfig(enabled=True, group_id_time_factor=0)
WITH_FLOOR = LinkedOrderManagerConfig(enabled=True)  # factor 100
NOW = _GROUP_ID_EPOCH + 1_000  # floor = 100_000


class HwmStore(SpyStore):
    """SpyStore with the optional HWM capability; every HWM write is logged."""

    def __init__(self, log: list[tuple[Any, ...]] | None = None) -> None:
        super().__init__(log)
        self.hwm: int | None = None
        self.fail_save = False

    def load_group_id_hwm(self) -> int | None:
        return self.hwm

    def save_group_id_hwm(self, group_id: int) -> None:
        if self.fail_save:
            msg = "disk full"
            raise OSError(msg)
        self.log.append(("save_hwm", group_id))
        self.hwm = group_id


def _mgr(
    venue: FakeEmulationVenue,
    codec: StringLinkIdCodec,
    clock: ManualClock,
    store: SpyStore,
    config: LinkedOrderManagerConfig,
) -> EmulatedLinkedOrderManager:
    return make_manager(venue, codec, clock, None, store, config)


def _gids(venue: FakeEmulationVenue) -> list[int]:
    tags = [str(c[3]) for c in venue.calls("place_leg")]
    return [int(re.match(r"hbl-(\d+)-", t).group(1)) for t in tags]  # type: ignore[union-attr]


async def test_hwm_survives_empty_store_and_no_open_orders(
    venue: FakeEmulationVenue, codec: StringLinkIdCodec, clock: ManualClock
) -> None:
    first = HwmStore(venue.call_log)
    m1 = _mgr(venue, codec, clock, first, NO_FLOOR)
    await m1.place_oco(TARGET, oco_spec())
    await m1.place_oco(TARGET, oco_spec())
    assert first.hwm == 2
    wiped = HwmStore(venue.call_log)
    wiped.hwm = first.hwm  # only the HWM survived
    m2 = _mgr(venue, codec, clock, wiped, NO_FLOOR)
    await m2.recover([])
    await m2.place_oco(TARGET, oco_spec())
    assert _gids(venue)[-1] == 3
    assert wiped.hwm == 3


async def test_time_floor_covers_store_without_hwm(
    venue: FakeEmulationVenue, codec: StringLinkIdCodec
) -> None:
    clock = ManualClock(NOW)
    m1 = _mgr(venue, codec, clock, SpyStore(venue.call_log), WITH_FLOOR)
    await m1.place_oco(TARGET, oco_spec())
    first = _gids(venue)[-1]
    assert first == 100_000
    clock.advance(60)
    m2 = _mgr(venue, codec, clock, SpyStore(venue.call_log), WITH_FLOOR)  # wiped, no HWM
    await m2.recover([])
    await m2.place_oco(TARGET, oco_spec())
    assert _gids(venue)[-1] > first


async def test_hwm_saved_before_placement(
    venue: FakeEmulationVenue, codec: StringLinkIdCodec, clock: ManualClock
) -> None:
    store = HwmStore(venue.call_log)
    await _mgr(venue, codec, clock, store, NO_FLOOR).place_oco(TARGET, oco_spec())
    names = [e[0] for e in venue.call_log]
    assert names.index("save_hwm") < names.index("place_leg")
    assert names.index("save_hwm") < names.index("save")


async def test_failed_hwm_save_places_nothing(
    venue: FakeEmulationVenue, codec: StringLinkIdCodec, clock: ManualClock
) -> None:
    store = HwmStore(venue.call_log)
    store.fail_save = True
    manager = _mgr(venue, codec, clock, store, NO_FLOOR)
    with pytest.raises(GroupIdPersistenceError) as info:
        await manager.place_oco(TARGET, oco_spec())
    assert isinstance(info.value, LinkedOrderError)
    assert venue.calls("place_leg") == []
    assert store.load_all() == []
    store.fail_save = False
    await manager.place_oco(TARGET, oco_spec())  # nothing was consumed
    assert _gids(venue)[-1] == 1


async def test_multiple_restarts_are_monotonic(
    venue: FakeEmulationVenue, codec: StringLinkIdCodec
) -> None:
    clock = ManualClock(NOW)
    hwm: int | None = None
    highest = 0
    for _ in range(4):
        store = HwmStore(venue.call_log)
        store.hwm = hwm
        manager = _mgr(venue, codec, clock, store, WITH_FLOOR)
        await manager.recover([])
        before = len(venue.calls("place_leg"))
        await manager.place_oco(TARGET, oco_spec())
        await manager.place_oco(TARGET, oco_spec())
        new = _gids(venue)[before:]
        assert min(new) > highest
        highest = max(new)
        hwm = store.hwm
        clock.advance(1)


async def test_factor_zero_disables_floor(
    venue: FakeEmulationVenue, codec: StringLinkIdCodec
) -> None:
    clock = ManualClock(NOW)
    await _mgr(venue, codec, clock, SpyStore(venue.call_log), NO_FLOOR).place_oco(
        TARGET, oco_spec()
    )
    assert _gids(venue)[-1] == 1


async def test_negative_floor_clamps_to_zero(
    venue: FakeEmulationVenue, codec: StringLinkIdCodec
) -> None:
    clock = ManualClock(_GROUP_ID_EPOCH - 10_000)
    await _mgr(venue, codec, clock, SpyStore(venue.call_log), WITH_FLOOR).place_oco(
        TARGET, oco_spec()
    )
    assert _gids(venue)[-1] == 1


GUARDED = LinkedOrderManagerConfig(
    enabled=True, group_id_time_factor=0, require_recover_before_place=True
)


async def test_guard_blocks_place_before_recover_without_io(
    venue: FakeEmulationVenue, codec: StringLinkIdCodec, clock: ManualClock
) -> None:
    store = HwmStore(venue.call_log)
    manager = _mgr(venue, codec, clock, store, GUARDED)
    with pytest.raises(RecoveryRequiredError):
        await manager.place_oco(TARGET, oco_spec())
    assert store.hwm is None
    assert store.saves == []
    assert venue.call_log == []
    await manager.recover([])
    await manager.place_oco(TARGET, oco_spec())
    assert _gids(venue)[-1] == 1


async def test_guard_off_by_default(
    venue: FakeEmulationVenue, codec: StringLinkIdCodec, clock: ManualClock
) -> None:
    assert LinkedOrderManagerConfig().require_recover_before_place is False
    await _mgr(venue, codec, clock, HwmStore(venue.call_log), NO_FLOOR).place_oco(
        TARGET, oco_spec()
    )
    assert _gids(venue)[-1] == 1


async def test_failed_recover_leaves_guard_set(
    venue: FakeEmulationVenue, codec: StringLinkIdCodec, clock: ManualClock
) -> None:
    store = HwmStore(venue.call_log)
    manager = _mgr(venue, codec, clock, store, GUARDED)

    def boom() -> list[Any]:
        msg = "store down"
        raise OSError(msg)

    store.load_all = boom  # type: ignore[method-assign]
    with pytest.raises(OSError, match="store down"):
        await manager.recover([])
    with pytest.raises(RecoveryRequiredError):
        await manager.place_oco(TARGET, oco_spec())


def test_negative_factor_rejected() -> None:
    with pytest.raises(ValueError, match="group_id_time_factor"):
        LinkedOrderManagerConfig(group_id_time_factor=-1)


async def test_store_without_hwm_still_satisfies_protocol_and_works(
    venue: FakeEmulationVenue, codec: StringLinkIdCodec, clock: ManualClock
) -> None:
    class Plain:
        durable = True

        def __init__(self) -> None:
            self.records: dict[int, Any] = {}

        def save(self, record: Any) -> None:
            self.records[record.group_id] = record

        def load_all(self) -> list[Any]:
            return list(self.records.values())

        def delete(self, group_id: int) -> None:
            self.records.pop(group_id, None)

    plain = Plain()
    assert isinstance(plain, LinkedGroupStore)
    assert not isinstance(plain, GroupIdHighWaterStore)
    manager = make_manager(venue, codec, clock, None, plain, NO_FLOOR)  # type: ignore[arg-type]
    await manager.place_oco(TARGET, oco_spec())
    assert _gids(venue)[-1] == 1
