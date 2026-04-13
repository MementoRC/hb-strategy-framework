"""Tests for SimpleEventBus."""
from __future__ import annotations

import pytest

from strategy_framework.orchestrator.simple_event_bus import SimpleEventBus
from strategy_framework.protocols.event_bus import EventBusProtocol


def test_satisfies_protocol():
    bus = SimpleEventBus()
    assert isinstance(bus, EventBusProtocol)


def test_subscribe_and_publish():
    bus = SimpleEventBus()
    received = []
    bus.subscribe("order.filled", lambda p: received.append(p))
    bus.publish("order.filled", {"order_id": "o1"})
    assert received == [{"order_id": "o1"}]


def test_multiple_handlers_same_event():
    bus = SimpleEventBus()
    results = []
    bus.subscribe("tick", lambda p: results.append("a"))
    bus.subscribe("tick", lambda p: results.append("b"))
    bus.publish("tick", {})
    assert sorted(results) == ["a", "b"]


def test_publish_unknown_event_is_noop():
    bus = SimpleEventBus()
    bus.publish("nonexistent", {})  # no error


def test_unsubscribe():
    bus = SimpleEventBus()
    received = []
    handler = lambda p: received.append(p)
    bus.subscribe("ev", handler)
    bus.unsubscribe("ev", handler)
    bus.publish("ev", {"x": 1})
    assert received == []


def test_unsubscribe_unknown_handler_is_noop():
    bus = SimpleEventBus()
    bus.unsubscribe("ev", lambda p: None)  # no error
