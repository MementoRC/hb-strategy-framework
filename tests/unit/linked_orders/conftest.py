"""Fixtures for linked-order tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from strategy_framework.testing.fake_linked_venue import (
    FakeEmulationVenue,
    ManualClock,
    RecordingEmitter,
    StringLinkIdCodec,
)
from tests.unit.linked_orders.manager_helpers import CONFIG, SpyStore, make_manager

if TYPE_CHECKING:
    from strategy_framework.linked_orders.manager import EmulatedLinkedOrderManager


@pytest.fixture
def venue() -> FakeEmulationVenue:
    return FakeEmulationVenue()


@pytest.fixture
def codec() -> StringLinkIdCodec:
    return StringLinkIdCodec()


@pytest.fixture
def clock() -> ManualClock:
    return ManualClock()


@pytest.fixture
def emitter() -> RecordingEmitter:
    return RecordingEmitter()


@pytest.fixture
def durable_store(venue: FakeEmulationVenue) -> SpyStore:
    """Durable store whose writes land in `venue.call_log` (to assert write-ahead order)."""
    return SpyStore(venue.call_log)


@pytest.fixture
def manager(
    venue: FakeEmulationVenue,
    codec: StringLinkIdCodec,
    clock: ManualClock,
    emitter: RecordingEmitter,
    durable_store: SpyStore,
) -> EmulatedLinkedOrderManager:
    return make_manager(venue, codec, clock, emitter, durable_store, CONFIG)
