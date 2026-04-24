"""Tests for DataRequirement primitive."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from strategy_framework.primitives.data_requirement import DataRequirement


def test_construction_with_all_fields():
    req = DataRequirement(
        source="binance_perpetual",
        trading_pair="BTC-USDT",
        interval="1m",
        max_records=200,
    )
    assert req.source == "binance_perpetual"
    assert req.trading_pair == "BTC-USDT"
    assert req.interval == "1m"
    assert req.max_records == 200


def test_max_records_defaults_to_100():
    req = DataRequirement(source="binance", trading_pair="ETH-USDT", interval="5m")
    assert req.max_records == 100


def test_frozen_immutability():
    req = DataRequirement(source="binance", trading_pair="BTC-USDT", interval="1m")
    with pytest.raises(ValidationError):
        req.source = "kraken"  # type: ignore[misc]


def test_equality():
    a = DataRequirement(source="binance", trading_pair="BTC-USDT", interval="1m")
    b = DataRequirement(source="binance", trading_pair="BTC-USDT", interval="1m")
    assert a == b


def test_hashable():
    req = DataRequirement(source="binance", trading_pair="BTC-USDT", interval="1m")
    assert hash(req) == hash(req)
    s = {req}
    assert req in s


def test_usable_in_list():
    reqs: list[DataRequirement] = [
        DataRequirement(source="binance", trading_pair="BTC-USDT", interval="1m"),
        DataRequirement(source="binance", trading_pair="ETH-USDT", interval="5m"),
    ]
    assert len(reqs) == 2
