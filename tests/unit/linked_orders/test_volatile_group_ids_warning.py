"""Volatile group ids (no allocator, no HWM store, flag off) log a WARNING (#108)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from strategy_framework.linked_orders.config import LinkedOrderManagerConfig
from strategy_framework.linked_orders.manager import EmulatedLinkedOrderManager
from strategy_framework.linked_orders.protocols import GroupIdHighWaterStore
from strategy_framework.linked_orders.store import InMemoryLinkedGroupStore
from tests.unit.linked_orders.test_group_id_allocator import FakeAllocator

if TYPE_CHECKING:
    import pytest

    from strategy_framework.linked_orders.protocols import GroupIdAllocator, LinkedGroupStore
    from strategy_framework.linked_orders.types import GroupRecord
    from strategy_framework.testing.fake_linked_venue import FakeEmulationVenue, StringLinkIdCodec

LOGGER = "strategy_framework.linked_orders.manager"


class PlainStore:
    """Minimal `LinkedGroupStore` without the high-water capability."""

    durable = True

    def __init__(self) -> None:
        self._records: dict[int, GroupRecord] = {}

    def save(self, record: GroupRecord) -> None:
        self._records[record.group_id] = record

    def load_all(self) -> list[GroupRecord]:
        return list(self._records.values())

    def delete(self, group_id: int) -> None:
        self._records.pop(group_id, None)


class PlainHwmStore(PlainStore):
    """Custom store with the high-water capability and no `group_id_hwm_durable` attribute."""

    def __init__(self) -> None:
        super().__init__()
        self._hwm: int | None = None

    def load_group_id_hwm(self) -> int | None:
        return self._hwm

    def save_group_id_hwm(self, group_id: int) -> None:
        self._hwm = group_id


def _build(
    venue: FakeEmulationVenue,
    codec: StringLinkIdCodec,
    *,
    store: LinkedGroupStore | None = None,
    allocator: GroupIdAllocator | None = None,
    allow: bool = False,
) -> EmulatedLinkedOrderManager:
    config = LinkedOrderManagerConfig(enabled=True, allow_volatile_group_ids=allow)
    return EmulatedLinkedOrderManager(
        venue, codec, config, store=store or PlainStore(), allocator=allocator
    )


def _volatile_warnings(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and "can repeat after a restart" in r.getMessage()
    ]


def test_default_flag_is_false() -> None:
    assert LinkedOrderManagerConfig().allow_volatile_group_ids is False


def test_volatile_default_warns_without_raising(
    venue: FakeEmulationVenue, codec: StringLinkIdCodec, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        _build(venue, codec)
    found = _volatile_warnings(caplog)
    assert len(found) == 1
    message = found[0].getMessage()
    for needle in (
        "allocator=",
        "GroupIdHighWaterStore",
        "allow_volatile_group_ids=True",
        "future release",
    ):
        assert needle in message


def test_allocator_does_not_warn(
    venue: FakeEmulationVenue, codec: StringLinkIdCodec, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        _build(venue, codec, allocator=FakeAllocator())
    assert not _volatile_warnings(caplog)


def test_hwm_store_without_durability_attribute_does_not_warn(
    venue: FakeEmulationVenue, codec: StringLinkIdCodec, caplog: pytest.LogCaptureFixture
) -> None:
    store = PlainHwmStore()
    assert isinstance(store, GroupIdHighWaterStore)
    assert not hasattr(store, "group_id_hwm_durable")
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        _build(venue, codec, store=store)
    assert not _volatile_warnings(caplog)


def test_hwm_store_declaring_non_durable_hwm_warns(
    venue: FakeEmulationVenue, codec: StringLinkIdCodec, caplog: pytest.LogCaptureFixture
) -> None:
    store = PlainHwmStore()
    store.group_id_hwm_durable = False
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        _build(venue, codec, store=store)
    assert len(_volatile_warnings(caplog)) == 1


def test_in_memory_store_warns(
    venue: FakeEmulationVenue, codec: StringLinkIdCodec, caplog: pytest.LogCaptureFixture
) -> None:
    assert InMemoryLinkedGroupStore.group_id_hwm_durable is False
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        _build(venue, codec, store=InMemoryLinkedGroupStore())
    assert len(_volatile_warnings(caplog)) == 1


def test_in_memory_store_with_opt_in_does_not_warn(
    venue: FakeEmulationVenue, codec: StringLinkIdCodec, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        _build(venue, codec, store=InMemoryLinkedGroupStore(), allow=True)
    assert not _volatile_warnings(caplog)


def test_explicit_opt_in_does_not_warn(
    venue: FakeEmulationVenue, codec: StringLinkIdCodec, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        _build(venue, codec, allow=True)
    assert not _volatile_warnings(caplog)
