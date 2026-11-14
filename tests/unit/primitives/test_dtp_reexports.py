"""Primitives re-exported from hb-data-type-primitives are the same objects (#50, #73)."""

import importlib

import data_type_primitives
import pytest

import strategy_framework
from strategy_framework import primitives
from strategy_framework.primitives import candle, order_book


def test_candle_data_is_dtp_class():
    assert candle.CandleData is data_type_primitives.CandleData
    assert strategy_framework.CandleData is data_type_primitives.CandleData


def test_order_book_entry_is_dtp_class():
    assert order_book.OrderBookEntry is data_type_primitives.OrderBookEntry
    assert strategy_framework.OrderBookEntry is data_type_primitives.OrderBookEntry


def test_order_book_snapshot_is_dtp_class():
    assert order_book.OrderBookSnapshot is data_type_primitives.OrderBookSnapshot
    assert strategy_framework.OrderBookSnapshot is data_type_primitives.OrderBookSnapshot


# primitive name -> data_type_primitives submodule that owns it
_DTP_MODULE = {
    "CandleData": "candle",
    "CloseType": "strategy_enums",
    "CreateExecutorAction": "executor_actions",
    "DataRequirement": "data_requirement",
    "ExecutorNotification": "notification",
    "OrderBookEntry": "order_book",
    "OrderBookSnapshot": "order_book",
    "OrderType": "strategy_enums",
    "PercentData": "percent",
    "RunnableStatus": "strategy_enums",
    "StopExecutorAction": "executor_actions",
    "StoreExecutorAction": "executor_actions",
    "TradeType": "strategy_enums",
    "TradingRules": "trading_rules",
    "TrailingStop": "trailing_stop",
    "TripleBarrierConfig": "triple_barrier",
    "UpdateExecutorAction": "executor_actions",
}


def _dtp_object(name: str) -> object:
    module = importlib.import_module(f"data_type_primitives.{_DTP_MODULE[name]}")
    return getattr(module, name)


@pytest.mark.parametrize("name", sorted(_DTP_MODULE))
def test_primitives_all_is_dtp_object(name):
    assert name in primitives.__all__
    assert getattr(primitives, name) is _dtp_object(name)


def test_primitives_all_fully_covered():
    assert set(primitives.__all__) == set(_DTP_MODULE)


def test_executor_action_base_is_dtp_class():
    from data_type_primitives import executor_actions

    from strategy_framework.primitives import actions

    assert actions._ExecutorAction is executor_actions._ExecutorAction


_TOP_LEVEL = [
    "CandleData",
    "CloseType",
    "CreateExecutorAction",
    "DataRequirement",
    "ExecutorNotification",
    "OrderBookEntry",
    "OrderBookSnapshot",
    "OrderType",
    "PercentData",
    "RunnableStatus",
    "StopExecutorAction",
    "TradeType",
    "TradingRules",
    "TrailingStop",
    "TripleBarrierConfig",
    "UpdateExecutorAction",
]


@pytest.mark.parametrize("name", _TOP_LEVEL)
def test_top_level_primitive_is_dtp_object(name):
    assert getattr(strategy_framework, name) is _dtp_object(name)


@pytest.mark.parametrize(
    ("dtp_name", "local_name"),
    [("StrategyTradeType", "TradeType"), ("StrategyOrderType", "OrderType")],
)
def test_dtp_strategy_aliases_are_framework_enums(dtp_name, local_name):
    assert getattr(data_type_primitives, dtp_name) is getattr(primitives, local_name)
