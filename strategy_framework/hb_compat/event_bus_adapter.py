"""EventBusAdapter — EventBusProtocol implementation delegating to event_bus.EventBus."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from event_bus import EventBus, Subscription

if TYPE_CHECKING:
    from collections.abc import Callable


class EventBusAdapter:
    """Thread-unsafe EventBusProtocol adapter over the ``event_bus`` sub-package.

    Delegates publish/subscribe/unsubscribe to an internal :class:`event_bus.EventBus`
    instance while presenting the same ``(event_type, handler)``-keyed surface as the
    former ``SimpleEventBus``. The underlying ``EventBus`` is not thread-safe; callers
    must synchronise external access if this adapter is shared across threads.
    """

    def __init__(self) -> None:
        self._bus = EventBus()
        self._subs: dict[tuple[str, Callable[[dict[str, Any]], None]], Subscription] = {}

    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        self._bus.publish(event_type, payload)

    def emit(self, event_type: str, payload: object) -> None:
        """Convenience alias for non-dict (e.g. dataclass) payloads.

        Bridges the ``emit(event_type, dataclass_instance)`` call convention used by
        ``ExecutorBase`` onto the canonical ``event_bus.EventBus``, which accepts any
        payload type despite :class:`EventBusProtocol` typing ``publish`` to ``dict``.
        """
        self._bus.publish(event_type, payload)

    def subscribe(self, event_type: str, handler: Callable[[dict[str, Any]], None]) -> None:
        self._subs[(event_type, handler)] = self._bus.subscribe(event_type, handler)

    def unsubscribe(self, event_type: str, handler: Callable[[dict[str, Any]], None]) -> None:
        sub = self._subs.pop((event_type, handler), None)
        if sub is not None:
            self._bus.unsubscribe(sub)
