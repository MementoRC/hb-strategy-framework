"""Canonical OrderType/TradeType invariants for order-placement Protocols."""

from decimal import Decimal

import pytest
from data_type_primitives import common, strategy_enums

from strategy_framework.testing.mock_market import MockMarketAccess

ORDER_TYPE_MEMBERS = list(strategy_enums.OrderType)
TRADE_TYPE_MEMBERS = list(strategy_enums.TradeType)


def test_order_type_names_subset_of_canonical():
    assert {m.name for m in strategy_enums.OrderType} <= {m.name for m in common.OrderType}


def test_trade_type_names_subset_of_canonical():
    assert {m.name for m in strategy_enums.TradeType} <= {m.name for m in common.TradeType}


@pytest.mark.parametrize("member", ORDER_TYPE_MEMBERS)
def test_order_type_round_trip(member):
    canonical = member.to_canonical()
    assert isinstance(canonical, common.OrderType)
    assert canonical.name == member.name
    assert strategy_enums.OrderType.from_canonical(canonical) is member


@pytest.mark.parametrize("member", TRADE_TYPE_MEMBERS)
def test_trade_type_round_trip(member):
    canonical = member.to_canonical()
    assert isinstance(canonical, common.TradeType)
    assert canonical.name == member.name
    assert strategy_enums.TradeType.from_canonical(canonical) is member


def test_mock_market_records_canonical_members():
    market = MockMarketAccess()
    market.place_order(common.OrderType.MARKET, common.TradeType.SELL, Decimal("1"), Decimal("1"))
    record = market.order_history[0]
    assert record["order_type"] is common.OrderType.MARKET
    assert record["side"] is common.TradeType.SELL
