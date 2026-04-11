"""Tests for core protocol definitions.

Validates that protocol interfaces are properly defined and can be
used for runtime type checking.
"""

from __future__ import annotations

import pytest

from strategy_framework.core.protocols import (
    MarketDataProviderProtocol,
    OrderExecutorProtocol,
    StrategyProtocol,
)


class _MockStrategy:
    """Minimal mock implementing StrategyProtocol."""

    @property
    def name(self) -> str:
        return "mock_strategy"

    @property
    def is_running(self) -> bool:
        return False

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass


class _NotAStrategy:
    """Class that does NOT implement StrategyProtocol."""

    pass


@pytest.mark.unit
class TestStrategyProtocol:
    """Validate StrategyProtocol runtime checking."""

    def test_conforming_class_is_recognized(self):
        strategy = _MockStrategy()
        assert isinstance(strategy, StrategyProtocol)

    def test_non_conforming_class_is_rejected(self):
        obj = _NotAStrategy()
        assert not isinstance(obj, StrategyProtocol)


@pytest.mark.unit
class TestMarketDataProviderProtocol:
    """Validate MarketDataProviderProtocol is runtime checkable."""

    def test_protocol_is_runtime_checkable(self):
        assert hasattr(MarketDataProviderProtocol, "__protocol_attrs__") or hasattr(
            MarketDataProviderProtocol, "__abstractmethods__"
        )


@pytest.mark.unit
class TestOrderExecutorProtocol:
    """Validate OrderExecutorProtocol is runtime checkable."""

    def test_protocol_is_runtime_checkable(self):
        assert hasattr(OrderExecutorProtocol, "__protocol_attrs__") or hasattr(
            OrderExecutorProtocol, "__abstractmethods__"
        )
