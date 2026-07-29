"""Tests for the hb_compat OrderType/TradeType canonical adapter."""

from __future__ import annotations

import pytest
from data_type_primitives.common import OrderType as CanonicalOrderType
from data_type_primitives.common import TradeType as CanonicalTradeType

from strategy_framework.hb_compat.common import OrderType, TradeType


class TestTradeType:
    def test_values_match_historical_primitives_enum(self) -> None:
        assert TradeType.BUY.value == "buy"
        assert TradeType.SELL.value == "sell"

    def test_opposite(self) -> None:
        assert TradeType.BUY.opposite == TradeType.SELL
        assert TradeType.SELL.opposite == TradeType.BUY

    def test_to_canonical(self) -> None:
        assert TradeType.BUY.to_canonical() is CanonicalTradeType.BUY
        assert TradeType.SELL.to_canonical() is CanonicalTradeType.SELL

    def test_from_canonical(self) -> None:
        assert TradeType.from_canonical(CanonicalTradeType.BUY) == TradeType.BUY
        assert TradeType.from_canonical(CanonicalTradeType.SELL) == TradeType.SELL

    def test_round_trip(self) -> None:
        for member in TradeType:
            assert TradeType.from_canonical(member.to_canonical()) == member


class TestOrderType:
    def test_values_match_historical_primitives_enum(self) -> None:
        assert OrderType.LIMIT.value == "limit"
        assert OrderType.MARKET.value == "market"
        assert OrderType.LIMIT_MAKER.value == "limit_maker"

    def test_to_canonical(self) -> None:
        assert OrderType.LIMIT.to_canonical() is CanonicalOrderType.LIMIT
        assert OrderType.MARKET.to_canonical() is CanonicalOrderType.MARKET
        assert OrderType.LIMIT_MAKER.to_canonical() is CanonicalOrderType.LIMIT_MAKER

    def test_from_canonical(self) -> None:
        assert OrderType.from_canonical(CanonicalOrderType.LIMIT) == OrderType.LIMIT
        assert OrderType.from_canonical(CanonicalOrderType.MARKET) == OrderType.MARKET
        assert OrderType.from_canonical(CanonicalOrderType.LIMIT_MAKER) == OrderType.LIMIT_MAKER

    def test_from_canonical_unrepresentable_member_raises(self) -> None:
        with pytest.raises(KeyError):
            OrderType.from_canonical(CanonicalOrderType.AMM_SWAP)

    def test_round_trip(self) -> None:
        for member in OrderType:
            assert OrderType.from_canonical(member.to_canonical()) == member
