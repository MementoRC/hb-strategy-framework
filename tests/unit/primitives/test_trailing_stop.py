"""Tests for TrailingStop — activation + delta with string serialization."""

from decimal import Decimal

import pytest

from strategy_framework.primitives.trailing_stop import TrailingStop


class TestTrailingStop:
    def test_creation(self):
        ts = TrailingStop(
            activation_price_pct=Decimal("0.015"), trailing_delta_pct=Decimal("0.005")
        )
        assert ts.activation_price_pct == Decimal("0.015")
        assert ts.trailing_delta_pct == Decimal("0.005")

    def test_from_string(self):
        """Parse compact string format: 'activation,delta'."""
        ts = TrailingStop.from_string("0.015,0.005")
        assert ts.activation_price_pct == Decimal("0.015")
        assert ts.trailing_delta_pct == Decimal("0.005")

    def test_to_string(self):
        ts = TrailingStop(
            activation_price_pct=Decimal("0.015"), trailing_delta_pct=Decimal("0.005")
        )
        assert ts.to_string() == "0.015,0.005"

    def test_roundtrip(self):
        original = TrailingStop(
            activation_price_pct=Decimal("0.025"),
            trailing_delta_pct=Decimal("0.010"),
        )
        parsed = TrailingStop.from_string(original.to_string())
        assert parsed == original

    def test_immutable(self):
        ts = TrailingStop(
            activation_price_pct=Decimal("0.015"), trailing_delta_pct=Decimal("0.005")
        )
        assert ts.model_config.get("frozen") is True

    def test_scale(self):
        ts = TrailingStop(
            activation_price_pct=Decimal("0.015"), trailing_delta_pct=Decimal("0.005")
        )
        scaled = ts.scale(Decimal("2.0"))
        assert scaled.activation_price_pct == Decimal("0.030")
        assert scaled.trailing_delta_pct == Decimal("0.010")

    def test_validation_positive(self):
        with pytest.raises(ValueError):
            TrailingStop(activation_price_pct=Decimal("-0.01"), trailing_delta_pct=Decimal("0.005"))
        with pytest.raises(ValueError):
            TrailingStop(activation_price_pct=Decimal("0.01"), trailing_delta_pct=Decimal("-0.005"))

    def test_from_string_invalid(self):
        with pytest.raises(ValueError, match="Expected format"):
            TrailingStop.from_string("invalid")
