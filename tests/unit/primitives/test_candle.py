"""Tests for CandleData frozen model."""

from decimal import Decimal

import pytest

from strategy_framework.primitives.candle import CandleData


class TestCandleData:
    """CandleData is an immutable OHLCV record."""

    def test_create_with_decimals(self):
        candle = CandleData(
            timestamp=1700000000000,
            open=Decimal("100.50"),
            high=Decimal("105.00"),
            low=Decimal("99.00"),
            close=Decimal("103.25"),
            volume=Decimal("1500.5"),
        )
        assert candle.timestamp == 1700000000000
        assert candle.open == Decimal("100.50")
        assert candle.high == Decimal("105.00")
        assert candle.low == Decimal("99.00")
        assert candle.close == Decimal("103.25")
        assert candle.volume == Decimal("1500.5")

    def test_frozen_immutable(self):
        candle = CandleData(
            timestamp=1700000000000,
            open=Decimal("100"),
            high=Decimal("105"),
            low=Decimal("99"),
            close=Decimal("103"),
            volume=Decimal("1500"),
        )
        with pytest.raises((AttributeError, ValueError)):
            candle.open = Decimal("999")

    def test_coerces_string_to_decimal(self):
        candle = CandleData(
            timestamp=1700000000000,
            open="100.50",
            high="105.00",
            low="99.00",
            close="103.25",
            volume="1500.5",
        )
        assert isinstance(candle.open, Decimal)
        assert candle.open == Decimal("100.50")

    def test_equality(self):
        kwargs = dict(
            timestamp=1700000000000,
            open=Decimal("100"),
            high=Decimal("105"),
            low=Decimal("99"),
            close=Decimal("103"),
            volume=Decimal("1500"),
        )
        assert CandleData(**kwargs) == CandleData(**kwargs)

    def test_different_timestamps_not_equal(self):
        base = dict(
            open=Decimal("100"),
            high=Decimal("105"),
            low=Decimal("99"),
            close=Decimal("103"),
            volume=Decimal("1500"),
        )
        assert CandleData(timestamp=1, **base) != CandleData(timestamp=2, **base)
