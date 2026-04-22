"""Tests for EventBusProtocol structural compliance."""

from __future__ import annotations

from strategy_framework.protocols.event_bus import EventBusProtocol


class ConcreteEventBus:
    def publish(self, event_type, payload):
        pass

    def subscribe(self, event_type, handler):
        pass

    def unsubscribe(self, event_type, handler):
        pass


def test_concrete_event_bus_satisfies_protocol():
    bus = ConcreteEventBus()
    assert isinstance(bus, EventBusProtocol)
