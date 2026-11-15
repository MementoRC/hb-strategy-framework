"""Tests A: opt-in, durable store, validation before the first I/O."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest
from data_type_primitives import OrderType

from strategy_framework.linked_orders.config import LinkedOrderManagerConfig
from strategy_framework.linked_orders.errors import (
    EmulationNotEnabledError,
    LinkedGroupNotFoundError,
    LinkIdCodecError,
    UnsupportedLegError,
    VolatileStoreError,
)
from strategy_framework.linked_orders.manager import EmulatedLinkedOrderManager
from strategy_framework.linked_orders.protocols import EmulationVenue
from strategy_framework.linked_orders.types import GroupState
from strategy_framework.protocols.lifecycle import ShutdownProtocol
from strategy_framework.testing.fake_linked_venue import FakeEmulationVenue, Int32LinkIdCodec
from tests.unit.linked_orders.builders import bracket_spec, oco_spec
from tests.unit.linked_orders.manager_helpers import TARGET, SpyStore, make_manager

if TYPE_CHECKING:
    from strategy_framework.testing.fake_linked_venue import ManualClock, StringLinkIdCodec

ENABLED = LinkedOrderManagerConfig(enabled=True)


def test_disabled_config_raises(venue: FakeEmulationVenue, codec: StringLinkIdCodec) -> None:
    with pytest.raises(EmulationNotEnabledError):
        EmulatedLinkedOrderManager(venue, codec, LinkedOrderManagerConfig())


async def test_default_store_is_volatile_and_refused(
    venue: FakeEmulationVenue, codec: StringLinkIdCodec
) -> None:
    manager = EmulatedLinkedOrderManager(venue, codec, ENABLED)
    with pytest.raises(VolatileStoreError):
        await manager.place_oco(TARGET, oco_spec())
    assert venue.call_log == []


async def test_volatile_store_allowed_when_opted_in_with_default_clock(
    venue: FakeEmulationVenue, codec: StringLinkIdCodec
) -> None:
    config = LinkedOrderManagerConfig(enabled=True, allow_volatile_store=True)
    manager = EmulatedLinkedOrderManager(venue, codec, config)
    handle = await manager.place_oco(TARGET, oco_spec())
    assert handle.state is GroupState.ARMED
    assert handle.emulated


async def test_kind_mismatch_is_value_error(manager: EmulatedLinkedOrderManager) -> None:
    with pytest.raises(ValueError, match="OCO"):
        await manager.place_bracket(TARGET, oco_spec())
    with pytest.raises(ValueError, match="BRACKET"):
        await manager.place_oco(TARGET, bracket_spec())


async def test_unsupported_leg_places_nothing(
    codec: StringLinkIdCodec, clock: ManualClock, durable_store: SpyStore
) -> None:
    venue = FakeEmulationVenue(native_types=[OrderType.LIMIT])
    manager = make_manager(venue, codec, clock, None, durable_store)
    with pytest.raises(UnsupportedLegError) as info:
        await manager.place_oco(TARGET, oco_spec())
    assert info.value.leg_index == 1
    assert venue.call_log == []
    assert durable_store.load_all() == []


class _Codec:
    """Configurable bad codec."""

    def __init__(self, mode: str) -> None:
        self.mode = mode

    def encode(self, group_id: int, leg_index: int) -> str | int:
        if self.mode == "encode_raises":
            raise RuntimeError
        return f"x{group_id}-{leg_index}"

    def decode(self, tag: str | int) -> tuple[int, int] | None:
        if self.mode == "decode_raises":
            raise RuntimeError
        if self.mode == "decode_none":
            return None
        return (999, 0)  # mismatch


@pytest.mark.parametrize("mode", ["encode_raises", "decode_raises", "decode_none", "mismatch"])
async def test_bad_codec_places_nothing(
    mode: str, venue: FakeEmulationVenue, clock: ManualClock, durable_store: SpyStore
) -> None:
    manager = EmulatedLinkedOrderManager(
        venue, _Codec(mode), ENABLED, store=durable_store, clock=clock
    )
    with pytest.raises(LinkIdCodecError):
        await manager.place_oco(TARGET, oco_spec())
    assert venue.call_log == []
    assert durable_store.load_all() == []


async def test_int32_overflow_is_refused(
    venue: FakeEmulationVenue, clock: ManualClock, durable_store: SpyStore
) -> None:
    config = LinkedOrderManagerConfig(enabled=True, group_id_seed=2**27)
    manager = EmulatedLinkedOrderManager(
        venue, Int32LinkIdCodec(), config, store=durable_store, clock=clock
    )
    with pytest.raises(LinkIdCodecError):
        await manager.place_oco(TARGET, oco_spec())
    assert venue.call_log == []


async def test_int32_codec_places_with_int_tags(
    venue: FakeEmulationVenue, clock: ManualClock, durable_store: SpyStore
) -> None:
    manager = EmulatedLinkedOrderManager(
        venue, Int32LinkIdCodec(), ENABLED, store=durable_store, clock=clock
    )
    handle = await manager.place_oco(TARGET, oco_spec())
    assert handle.state is GroupState.ARMED
    assert [c[3] for c in venue.calls("place_leg")] == ["16", "17"]


async def test_options_are_ignored_and_logged(
    manager: EmulatedLinkedOrderManager, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        handle = await manager.place_oco(TARGET, oco_spec(), options={"post_only": True})
    assert handle.state is GroupState.ARMED
    assert "post_only" in caplog.text


def test_unknown_group_raises(manager: EmulatedLinkedOrderManager) -> None:
    for bad in ("42", "not-a-number"):
        with pytest.raises(LinkedGroupNotFoundError):
            manager.get_handle(bad)


def test_protocol_conformance(
    manager: EmulatedLinkedOrderManager, venue: FakeEmulationVenue
) -> None:
    assert isinstance(manager, ShutdownProtocol)
    assert isinstance(venue, EmulationVenue)
