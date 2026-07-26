from __future__ import annotations

from decimal import Decimal

import pytest

from strategy_framework.executors.events import (
    OrderCancelledEvent,
    OrderFailedEvent,
    OrderFilledEvent,
    PriceUpdatedEvent,
)
from strategy_framework.hb_compat import EventBusAdapter


class TestEventDataclasses:
    def test_order_filled_event_is_frozen(self) -> None:
        evt = OrderFilledEvent(order_id="o1", price=Decimal("100"), amount=Decimal("1"))
        with pytest.raises((AttributeError, TypeError)):
            evt.order_id = "other"  # type: ignore[misc]

    def test_order_filled_event_fields(self) -> None:
        evt = OrderFilledEvent(order_id="o1", price=Decimal("100"), amount=Decimal("1"))
        assert evt.order_id == "o1"
        assert evt.price == Decimal("100")
        assert evt.amount == Decimal("1")

    def test_price_updated_event(self) -> None:
        evt = PriceUpdatedEvent(price=Decimal("50000"))
        assert evt.price == Decimal("50000")

    def test_order_cancelled_event(self) -> None:
        evt = OrderCancelledEvent(order_id="o2")
        assert evt.order_id == "o2"

    def test_order_failed_event(self) -> None:
        evt = OrderFailedEvent(order_id="o3", reason="timeout")
        assert evt.order_id == "o3"
        assert evt.reason == "timeout"


class TestEventBus:
    def test_subscribe_and_emit(self) -> None:
        bus = EventBusAdapter()
        received: list[OrderFilledEvent] = []
        bus.subscribe("order.filled", received.append)
        evt = OrderFilledEvent(order_id="o1", price=Decimal("100"), amount=Decimal("1"))
        bus.emit("order.filled", evt)
        assert received == [evt]

    def test_unsubscribe(self) -> None:
        bus = EventBusAdapter()
        received: list[object] = []
        handler = received.append
        bus.subscribe("order.filled", handler)
        bus.unsubscribe("order.filled", handler)
        bus.emit("order.filled", OrderFilledEvent("o1", Decimal("1"), Decimal("1")))
        assert received == []

    def test_multiple_handlers_called_in_order(self) -> None:
        bus = EventBusAdapter()
        order: list[str] = []
        bus.subscribe("ev", lambda _: order.append("first"))
        bus.subscribe("ev", lambda _: order.append("second"))
        bus.emit("ev", "payload")
        assert order == ["first", "second"]

    def test_handler_exception_does_not_stop_others(self) -> None:
        bus = EventBusAdapter()
        reached: list[bool] = []

        def bad_handler(_: object) -> None:
            raise RuntimeError("boom")

        bus.subscribe("ev", bad_handler)
        bus.subscribe("ev", lambda _: reached.append(True))
        bus.emit("ev", "payload")  # must not raise
        assert reached == [True]

    def test_emit_unknown_event_type_is_noop(self) -> None:
        bus = EventBusAdapter()
        bus.emit("no.subscribers", "payload")  # must not raise

    def test_unsubscribe_nonexistent_handler_is_noop(self) -> None:
        bus = EventBusAdapter()
        bus.unsubscribe("ev", lambda _: None)  # must not raise
