"""Tests for TripleBarrierConfig."""

from decimal import Decimal

import pytest

from strategy_framework.primitives.triple_barrier import TripleBarrierConfig


class TestTripleBarrierConfig:
    def test_creation(self):
        config = TripleBarrierConfig(
            stop_loss=Decimal("0.03"),
            take_profit=Decimal("0.05"),
            time_limit_s=3600,
        )
        assert config.stop_loss == Decimal("0.03")
        assert config.take_profit == Decimal("0.05")
        assert config.time_limit_s == 3600

    def test_defaults(self):
        config = TripleBarrierConfig()
        assert config.stop_loss == Decimal("0")
        assert config.take_profit == Decimal("0")
        assert config.time_limit_s == 0

    def test_has_stop_loss(self):
        config = TripleBarrierConfig(stop_loss=Decimal("0.03"))
        assert config.has_stop_loss
        assert not TripleBarrierConfig().has_stop_loss

    def test_has_take_profit(self):
        config = TripleBarrierConfig(take_profit=Decimal("0.05"))
        assert config.has_take_profit
        assert not TripleBarrierConfig().has_take_profit

    def test_has_time_limit(self):
        config = TripleBarrierConfig(time_limit_s=3600)
        assert config.has_time_limit
        assert not TripleBarrierConfig().has_time_limit

    def test_scale_by_volatility(self):
        """Barriers can be scaled by a volatility factor."""
        config = TripleBarrierConfig(
            stop_loss=Decimal("0.03"),
            take_profit=Decimal("0.05"),
            time_limit_s=3600,
        )
        scaled = config.scale(Decimal("2.0"))
        assert scaled.stop_loss == Decimal("0.06")
        assert scaled.take_profit == Decimal("0.10")
        assert scaled.time_limit_s == 3600  # time not scaled

    def test_immutable(self):
        config = TripleBarrierConfig(stop_loss=Decimal("0.03"))
        assert config.model_config.get("frozen") is True

    def test_validation_non_negative(self):
        with pytest.raises(ValueError):
            TripleBarrierConfig(stop_loss=Decimal("-0.01"))
        with pytest.raises(ValueError):
            TripleBarrierConfig(take_profit=Decimal("-0.01"))
        with pytest.raises(ValueError):
            TripleBarrierConfig(time_limit_s=-1)
