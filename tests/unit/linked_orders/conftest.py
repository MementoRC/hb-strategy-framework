"""Fixtures for linked-order tests."""

from __future__ import annotations

import pytest

from strategy_framework.linked_orders.store import InMemoryLinkedGroupStore
from strategy_framework.testing.fake_linked_venue import (
    FakeEmulationVenue,
    ManualClock,
    RecordingEmitter,
    StringLinkIdCodec,
)


class DurableInMemoryStore(InMemoryLinkedGroupStore):
    """In-memory store that claims durability (for opt-out-free tests)."""

    @property
    def durable(self) -> bool:
        return True


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
def durable_store() -> DurableInMemoryStore:
    return DurableInMemoryStore()
