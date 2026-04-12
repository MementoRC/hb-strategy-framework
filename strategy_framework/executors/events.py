from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OrderFilledEvent:
    order_id: str
    price: Decimal
    amount: Decimal


@dataclass(frozen=True)
class OrderCancelledEvent:
    order_id: str


@dataclass(frozen=True)
class OrderFailedEvent:
    order_id: str
    reason: str


@dataclass(frozen=True)
class PriceUpdatedEvent:
    price: Decimal


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[[Any], None]]] = {}

    def subscribe(self, event_type: str, handler: Callable[[Any], None]) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    def unsubscribe(self, event_type: str, handler: Callable[[Any], None]) -> None:
        handlers = self._handlers.get(event_type, [])
        try:
            handlers.remove(handler)
        except ValueError:
            pass

    def emit(self, event_type: str, event: Any) -> None:
        """Dispatch event to all registered handlers.

        Exceptions raised by individual handlers are logged and suppressed so
        that one failing handler cannot prevent others from receiving the event.
        """
        for handler in list(self._handlers.get(event_type, [])):
            try:
                handler(event)
            except Exception:
                logger.exception("EventBus handler raised for event type %r", event_type)
