"""Tests for hb_compat data types.

Validates Pydantic models for Hummingbot compatibility.
"""

from __future__ import annotations

import pytest

from strategy_framework.hb_compat.data_types import StrategyConfig, UnsupportedStrategyError


@pytest.mark.unit
class TestStrategyConfig:
    """Validate StrategyConfig Pydantic model."""

    def test_create_valid_config(self):
        config = StrategyConfig(
            strategy_name="pure_market_making",
            trading_pair="BTC-USDT",
            exchange="binance",
        )
        assert config.strategy_name == "pure_market_making"
        assert config.trading_pair == "BTC-USDT"
        assert config.exchange == "binance"

    def test_config_requires_all_fields(self):
        with pytest.raises(Exception):
            StrategyConfig(strategy_name="test")  # type: ignore[call-arg]


@pytest.mark.unit
class TestUnsupportedStrategyError:
    """Validate custom exception."""

    def test_is_exception(self):
        assert issubclass(UnsupportedStrategyError, Exception)

    def test_can_raise_with_message(self):
        with pytest.raises(UnsupportedStrategyError, match="not supported"):
            raise UnsupportedStrategyError("Strategy 'foo' is not supported")
