"""Tests for TradingRules frozen model."""

from decimal import Decimal

import pytest

from strategy_framework.primitives.trading_rules import TradingRules


class TestTradingRules:
    """TradingRules captures exchange constraints for a trading pair."""

    def test_create_with_defaults(self):
        rules = TradingRules(trading_pair="BTC-USDT")
        assert rules.trading_pair == "BTC-USDT"
        assert rules.min_order_size == Decimal("0")
        assert rules.min_price_increment == Decimal("0")
        assert rules.min_base_amount_increment == Decimal("0")
        assert rules.min_notional_size == Decimal("0")
        assert rules.supports_limit_orders is True
        assert rules.supports_market_orders is True

    def test_create_with_all_fields(self):
        rules = TradingRules(
            trading_pair="ETH-USDT",
            min_order_size=Decimal("0.001"),
            max_order_size=Decimal("1000"),
            min_price_increment=Decimal("0.01"),
            min_base_amount_increment=Decimal("0.001"),
            min_notional_size=Decimal("10"),
            supports_limit_orders=True,
            supports_market_orders=False,
        )
        assert rules.min_order_size == Decimal("0.001")
        assert rules.max_order_size == Decimal("1000")
        assert rules.supports_market_orders is False

    def test_frozen(self):
        rules = TradingRules(trading_pair="BTC-USDT")
        with pytest.raises((AttributeError, ValueError)):
            rules.trading_pair = "ETH-USDT"

    def test_coerces_strings(self):
        rules = TradingRules(
            trading_pair="BTC-USDT",
            min_order_size="0.001",
            min_price_increment="0.01",
        )
        assert isinstance(rules.min_order_size, Decimal)
        assert rules.min_order_size == Decimal("0.001")

    def test_max_order_size_none_default(self):
        rules = TradingRules(trading_pair="BTC-USDT")
        assert rules.max_order_size is None
