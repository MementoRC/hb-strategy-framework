"""Primitives re-exported from hb-data-type-primitives are the same objects (#50)."""

import data_type_primitives

import strategy_framework
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
