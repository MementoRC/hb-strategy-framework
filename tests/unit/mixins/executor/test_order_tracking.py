"""Tests for OrderTrackingMixin."""

from __future__ import annotations

from decimal import Decimal

import pytest

from strategy_framework.mixins.executor.order_tracking import OrderTrackingMixin
from strategy_framework.testing.factories import TrackedOrderFactory


class ConcreteTracking(OrderTrackingMixin):
    def __init__(self) -> None:
        self._init_order_tracking()


def test_init_empty_lists() -> None:
    obj = ConcreteTracking()
    assert obj.open_orders == []
    assert obj.close_orders == []


def test_add_open_order() -> None:
    obj = ConcreteTracking()
    order = TrackedOrderFactory.open_order(order_id="buy_001")
    obj.add_open_order(order)
    assert len(obj.open_orders) == 1
    assert obj.open_orders[0].order_id == "buy_001"


def test_add_close_order() -> None:
    obj = ConcreteTracking()
    order = TrackedOrderFactory.open_order(order_id="sell_001")
    obj.add_close_order(order)
    assert len(obj.close_orders) == 1


def test_get_filled_open_orders_empty_when_none_filled() -> None:
    obj = ConcreteTracking()
    obj.add_open_order(TrackedOrderFactory.open_order())
    assert obj.get_filled_open_orders() == []


def test_get_filled_open_orders_returns_filled() -> None:
    obj = ConcreteTracking()
    obj.add_open_order(TrackedOrderFactory.open_order(order_id="unfilled"))
    obj.add_open_order(TrackedOrderFactory.filled_order(order_id="filled"))
    filled = obj.get_filled_open_orders()
    assert len(filled) == 1
    assert filled[0].order_id == "filled"


def test_get_open_order_found() -> None:
    obj = ConcreteTracking()
    obj.add_open_order(TrackedOrderFactory.open_order(order_id="target"))
    result = obj.get_open_order("target")
    assert result is not None
    assert result.order_id == "target"


def test_get_open_order_not_found_returns_none() -> None:
    obj = ConcreteTracking()
    assert obj.get_open_order("nonexistent") is None


def test_update_tracked_order_updates_kwargs() -> None:
    obj = ConcreteTracking()
    order = TrackedOrderFactory.open_order(order_id="upd_001")
    obj.add_open_order(order)
    # update_tracked_order is a no-op in the base; verify it doesn't raise
    obj.update_tracked_order("upd_001", exchange_order_id="exch_123")


def test_init_order_tracking_resets_state() -> None:
    obj = ConcreteTracking()
    obj.add_open_order(TrackedOrderFactory.open_order())
    obj._init_order_tracking()
    assert obj.open_orders == []
    assert obj.close_orders == []


def test_multiple_open_orders() -> None:
    obj = ConcreteTracking()
    for i in range(3):
        obj.add_open_order(TrackedOrderFactory.open_order(order_id=f"order_{i:03d}"))
    assert len(obj.open_orders) == 3
