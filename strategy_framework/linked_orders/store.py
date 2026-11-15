"""In-memory group store (not durable: tests and explicit opt-in only)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from strategy_framework.linked_orders.types import GroupId, GroupRecord


class InMemoryLinkedGroupStore:
    """Dict-backed `LinkedGroupStore`. `durable` is False: it does not survive a restart."""

    def __init__(self) -> None:
        self._records: dict[GroupId, GroupRecord] = {}

    @property
    def durable(self) -> bool:
        return False

    def save(self, record: GroupRecord) -> None:
        self._records[record.group_id] = record

    def load_all(self) -> Sequence[GroupRecord]:
        return [self._records[k] for k in sorted(self._records)]

    def delete(self, group_id: GroupId) -> None:
        self._records.pop(group_id, None)
