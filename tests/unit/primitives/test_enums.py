"""Tests for strategy framework enums."""

from strategy_framework.primitives.enums import (
    CloseType,
    OrderType,
    RunnableStatus,
    TradeType,
)


class TestCloseType:
    def test_close_type_values(self):
        assert CloseType.STOP_LOSS.value == "stop_loss"
        assert CloseType.TAKE_PROFIT.value == "take_profit"
        assert CloseType.TIME_LIMIT.value == "time_limit"
        assert CloseType.TRAILING_STOP.value == "trailing_stop"
        assert CloseType.EARLY_STOP.value == "early_stop"
        assert CloseType.EXPIRED.value == "expired"
        assert CloseType.FAILED.value == "failed"

    def test_close_type_is_terminal(self):
        """Terminal close types mean the executor is done."""
        assert CloseType.STOP_LOSS.is_terminal
        assert CloseType.TAKE_PROFIT.is_terminal
        assert CloseType.FAILED.is_terminal
        assert not CloseType.TRAILING_STOP.is_terminal


class TestTradeType:
    def test_trade_type_values(self):
        assert TradeType.BUY.value == "buy"
        assert TradeType.SELL.value == "sell"

    def test_opposite(self):
        assert TradeType.BUY.opposite == TradeType.SELL
        assert TradeType.SELL.opposite == TradeType.BUY


class TestOrderType:
    def test_order_type_values(self):
        assert OrderType.LIMIT.value == "limit"
        assert OrderType.MARKET.value == "market"
        assert OrderType.LIMIT_MAKER.value == "limit_maker"


class TestRunnableStatus:
    def test_status_values(self):
        assert RunnableStatus.NOT_STARTED.value == "not_started"
        assert RunnableStatus.RUNNING.value == "running"
        assert RunnableStatus.SHUTTING_DOWN.value == "shutting_down"
        assert RunnableStatus.TERMINATED.value == "terminated"

    def test_is_active(self):
        assert not RunnableStatus.NOT_STARTED.is_active
        assert RunnableStatus.RUNNING.is_active
        assert RunnableStatus.SHUTTING_DOWN.is_active
        assert not RunnableStatus.TERMINATED.is_active
