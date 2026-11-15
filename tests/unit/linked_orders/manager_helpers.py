"""Helpers shared by the manager-level tests (stores that log, managers, task spinning)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from strategy_framework.linked_orders.config import LinkedOrderManagerConfig
from strategy_framework.linked_orders.events import LinkedEventKind, LinkedGroupEvent
from strategy_framework.linked_orders.manager import EmulatedLinkedOrderManager
from strategy_framework.linked_orders.store import InMemoryLinkedGroupStore

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from strategy_framework.linked_orders.types import GroupRecord, LegRecord
    from strategy_framework.testing.fake_linked_venue import (
        FakeEmulationVenue,
        ManualClock,
        RecordingEmitter,
        StringLinkIdCodec,
    )

CONFIG = LinkedOrderManagerConfig(enabled=True)
TARGET = "BTC-USD"


class SpyStore(InMemoryLinkedGroupStore):
    """Durable-looking in-memory store that logs every write into a shared call log."""

    def __init__(self, log: list[tuple[Any, ...]] | None = None) -> None:
        super().__init__()
        self.log: list[tuple[Any, ...]] = log if log is not None else []
        self.saves: list[GroupRecord] = []
        self.deletes: list[int] = []

    @property
    def durable(self) -> bool:
        return True

    def save(self, record: GroupRecord) -> None:
        self.saves.append(record)
        legs = tuple((str(leg.link_tag), leg.status.name) for leg in record.legs)
        self.log.append(("save", record.group_id, legs, len(self.saves) - 1))
        super().save(record)

    def delete(self, group_id: int) -> None:
        self.deletes.append(group_id)
        self.log.append(("delete", group_id))
        super().delete(group_id)


def make_manager(
    venue: FakeEmulationVenue,
    codec: StringLinkIdCodec,
    clock: ManualClock,
    emitter: RecordingEmitter | None,
    store: SpyStore,
    config: LinkedOrderManagerConfig = CONFIG,
) -> EmulatedLinkedOrderManager:
    return EmulatedLinkedOrderManager(venue, codec, config, store=store, clock=clock, bus=emitter)


async def spin(rounds: int = 10) -> None:
    """Let every runnable task advance until it blocks."""
    for _ in range(rounds):
        await asyncio.sleep(0)


def spawn[T](coro: Coroutine[Any, Any, T]) -> asyncio.Task[T]:
    return asyncio.get_running_loop().create_task(coro)


def record(manager: EmulatedLinkedOrderManager, group_id: int = 1) -> GroupRecord:
    return manager._groups[group_id].record  # noqa: SLF001


def leg(manager: EmulatedLinkedOrderManager, index: int, group_id: int = 1) -> LegRecord:
    return record(manager, group_id).legs[index]


def events(emitter: RecordingEmitter, kind: LinkedEventKind) -> list[LinkedGroupEvent]:
    return [p for p in emitter.payloads() if isinstance(p, LinkedGroupEvent) and p.kind is kind]


def assert_write_ahead(log: list[tuple[Any, ...]]) -> None:
    """I7: every place_leg is preceded by a save holding that tag as PENDING_CREATE."""
    for position, entry in enumerate(log):
        if entry[0] != "place_leg":
            continue
        tag = entry[3]
        earlier = [e for e in log[:position] if e[0] == "save"]
        assert any((tag, "PENDING_CREATE") in e[2] for e in earlier), f"no write-ahead for {tag}"
