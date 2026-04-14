"""SimpleEventBus — minimal in-memory EventBusProtocol implementation."""

from __future__ import annotations

import contextlib
from collections import defaultdict
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


class SimpleEventBus:
    """Thread-unsafe in-memory event bus. Suitable for single-threaded strategies."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[[dict[str, Any]], None]]] = defaultdict(list)

    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        for handler in list(self._handlers.get(event_type, [])):
            handler(payload)

    def subscribe(self, event_type: str, handler: Callable[[dict[str, Any]], None]) -> None:
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        handlers = self._handlers.get(event_type, [])
        with contextlib.suppress(ValueError):
            handlers.remove(handler)
