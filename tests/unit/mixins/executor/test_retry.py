"""Tests for RetryMixin."""

from __future__ import annotations

import pytest

from strategy_framework.mixins.executor.retry import RetryMixin
from strategy_framework.protocols.composites import RetryProtocol


class ConcreteRetry(RetryMixin):
    max_retries: int = 3

    def __init__(self) -> None:
        self._init_retry()


def test_init_sets_current_retries_to_zero() -> None:
    obj = ConcreteRetry()
    assert obj.current_retries == 0


def test_increment_retries_advances_counter() -> None:
    obj = ConcreteRetry()
    obj.increment_retries()
    assert obj.current_retries == 1


def test_increment_retries_accumulates() -> None:
    obj = ConcreteRetry()
    obj.increment_retries()
    obj.increment_retries()
    assert obj.current_retries == 2


def test_has_not_exceeded_below_limit() -> None:
    obj = ConcreteRetry()
    obj.increment_retries()
    assert obj.has_exceeded_max_retries() is False


def test_has_exceeded_at_exactly_max_retries() -> None:
    obj = ConcreteRetry()
    for _ in range(3):
        obj.increment_retries()
    assert obj.has_exceeded_max_retries() is True


def test_has_exceeded_beyond_max_retries() -> None:
    obj = ConcreteRetry()
    for _ in range(5):
        obj.increment_retries()
    assert obj.has_exceeded_max_retries() is True


def test_init_retry_resets_state() -> None:
    obj = ConcreteRetry()
    obj.increment_retries()
    obj.increment_retries()
    obj._init_retry()
    assert obj.current_retries == 0


def test_zero_max_retries_exceeds_immediately() -> None:
    class ZeroRetry(RetryMixin):
        max_retries: int = 0

        def __init__(self) -> None:
            self._init_retry()

    obj = ZeroRetry()
    assert obj.has_exceeded_max_retries() is True


def test_satisfies_retry_protocol() -> None:
    obj = ConcreteRetry()
    assert isinstance(obj, RetryProtocol)
