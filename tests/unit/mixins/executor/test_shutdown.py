"""Tests for ShutdownMixin."""

from __future__ import annotations

import pytest

from strategy_framework.mixins.executor.shutdown import ShutdownMixin


class ConcreteShutdown(ShutdownMixin):
    """Concrete shutdown with controllable pending-order state."""

    def __init__(self, pending: bool = False) -> None:
        self._pending = pending
        self._init_shutdown()

    @property
    def has_pending_orders(self) -> bool:
        return self._pending


def test_init_shutdown_requested_false() -> None:
    obj = ConcreteShutdown()
    assert obj.shutdown_requested is False


def test_request_shutdown_sets_flag() -> None:
    obj = ConcreteShutdown()
    obj.request_shutdown()
    assert obj.shutdown_requested is True


def test_request_shutdown_idempotent() -> None:
    obj = ConcreteShutdown()
    obj.request_shutdown()
    obj.request_shutdown()
    assert obj.shutdown_requested is True


def test_has_pending_orders_delegates_to_host() -> None:
    obj_with = ConcreteShutdown(pending=True)
    obj_without = ConcreteShutdown(pending=False)
    assert obj_with.has_pending_orders is True
    assert obj_without.has_pending_orders is False


def test_init_shutdown_resets_state() -> None:
    obj = ConcreteShutdown()
    obj.request_shutdown()
    obj._init_shutdown()
    assert obj.shutdown_requested is False


def test_has_pending_orders_abstract_raises_if_not_overridden() -> None:
    """ShutdownMixin.has_pending_orders must be overridden."""
    obj = ShutdownMixin()
    obj._init_shutdown()
    with pytest.raises(NotImplementedError):
        _ = obj.has_pending_orders
