"""Tests for EventBusAdapter."""

from __future__ import annotations

from strategy_framework.hb_compat.event_bus_adapter import EventBusAdapter
from strategy_framework.protocols.event_bus import EventBusProtocol


def test_satisfies_protocol():
    bus = EventBusAdapter()
    assert isinstance(bus, EventBusProtocol)


def test_subscribe_and_publish():
    bus = EventBusAdapter()
    received = []
    bus.subscribe("order.filled", lambda p: received.append(p))
    bus.publish("order.filled", {"order_id": "o1"})
    assert received == [{"order_id": "o1"}]


def test_multiple_handlers_same_event():
    bus = EventBusAdapter()
    results = []
    bus.subscribe("tick", lambda p: results.append("a"))
    bus.subscribe("tick", lambda p: results.append("b"))
    bus.publish("tick", {})
    assert sorted(results) == ["a", "b"]


def test_publish_unknown_event_is_noop():
    bus = EventBusAdapter()
    bus.publish("nonexistent", {})  # no error


def test_unsubscribe():
    bus = EventBusAdapter()
    received = []

    def handler(p):
        received.append(p)

    bus.subscribe("ev", handler)
    bus.unsubscribe("ev", handler)
    bus.publish("ev", {"x": 1})
    assert received == []


def test_unsubscribe_unknown_handler_is_noop():
    bus = EventBusAdapter()
    bus.unsubscribe("ev", lambda p: None)  # no error


def test_unsubscribe_never_subscribed_event_type_is_noop():
    bus = EventBusAdapter()

    def handler(p):
        pass

    bus.unsubscribe("never.subscribed", handler)  # event_type never seen; no error
