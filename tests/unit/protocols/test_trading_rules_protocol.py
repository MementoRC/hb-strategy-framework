"""Tests for TradingRulesProtocol structural typing."""

from decimal import Decimal

from strategy_framework.primitives.trading_rules import TradingRules
from strategy_framework.protocols.trading_rules import TradingRulesProtocol


class ConcreteTradingRules:
    """Minimal implementation satisfying TradingRulesProtocol."""

    def get_trading_rules(self, trading_pair: str) -> TradingRules:
        return TradingRules(
            trading_pair=trading_pair,
            min_order_size=Decimal("0.001"),
            min_price_increment=Decimal("0.01"),
            min_base_amount_increment=Decimal("0.001"),
            min_notional_size=Decimal("10"),
        )

    def quantize_order_amount(self, trading_pair: str, amount: Decimal) -> Decimal:
        rules = self.get_trading_rules(trading_pair)
        if rules.min_base_amount_increment > 0:
            return (amount // rules.min_base_amount_increment) * rules.min_base_amount_increment
        return amount

    def quantize_order_price(self, trading_pair: str, price: Decimal) -> Decimal:
        rules = self.get_trading_rules(trading_pair)
        if rules.min_price_increment > 0:
            return (price // rules.min_price_increment) * rules.min_price_increment
        return price


class TestTradingRulesProtocol:
    """TradingRulesProtocol is runtime-checkable and structurally typed."""

    def test_concrete_satisfies_protocol(self):
        provider = ConcreteTradingRules()
        assert isinstance(provider, TradingRulesProtocol)

    def test_get_trading_rules(self):
        provider = ConcreteTradingRules()
        rules = provider.get_trading_rules("BTC-USDT")
        assert isinstance(rules, TradingRules)
        assert rules.trading_pair == "BTC-USDT"
        assert rules.min_order_size == Decimal("0.001")

    def test_quantize_order_amount(self):
        provider = ConcreteTradingRules()
        quantized = provider.quantize_order_amount("BTC-USDT", Decimal("1.23456"))
        assert quantized == Decimal("1.234")

    def test_quantize_order_price(self):
        provider = ConcreteTradingRules()
        quantized = provider.quantize_order_price("BTC-USDT", Decimal("100.567"))
        assert quantized == Decimal("100.56")

    def test_incomplete_impl_fails_check(self):
        class Incomplete:
            def get_trading_rules(self, trading_pair: str) -> TradingRules:
                return TradingRules(trading_pair=trading_pair)

        assert not isinstance(Incomplete(), TradingRulesProtocol)
