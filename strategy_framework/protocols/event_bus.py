"""EventBusProtocol — optional publish/subscribe scaffold."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Callable


@runtime_checkable
class EventBusProtocol(Protocol):
    """Minimal event bus interface. String-typed events (e.g. 'executor.completed')."""

    def publish(  # pragma: no cover
        self, event_type: str, payload: dict[str, Any]
    ) -> None: ...

    def subscribe(  # pragma: no cover
        self, event_type: str, handler: Callable[[dict[str, Any]], None]
    ) -> None: ...

    def unsubscribe(  # pragma: no cover
        self, event_type: str, handler: Callable[[dict[str, Any]], None]
    ) -> None: ...
