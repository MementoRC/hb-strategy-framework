"""Tests for PercentData — hashable, comparable Decimal wrapper."""

from decimal import Decimal

import pytest

from strategy_framework.primitives.percent import PercentData


class TestPercentData:
    def test_creation_from_string(self):
        p = PercentData("0.015")
        assert p.value == Decimal("0.015")

    def test_creation_from_decimal(self):
        p = PercentData(Decimal("0.5"))
        assert p.value == Decimal("0.5")

    def test_creation_from_float(self):
        p = PercentData(0.015)
        assert p.value == Decimal("0.015")

    def test_quantization(self):
        """Values are quantized to 6 decimal places."""
        p = PercentData("0.0123456789")
        assert p.value == Decimal("0.012346")

    def test_hashable(self):
        """PercentData can be used as dict keys."""
        p1 = PercentData("0.015")
        p2 = PercentData("0.015")
        d = {p1: "first"}
        assert d[p2] == "first"

    def test_equality(self):
        assert PercentData("0.015") == PercentData("0.015")
        assert PercentData("0.015") != PercentData("0.020")

    def test_ordering(self):
        p1 = PercentData("0.01")
        p2 = PercentData("0.05")
        p3 = PercentData("0.10")
        assert p1 < p2 < p3
        assert p3 > p2 > p1
        assert p1 <= p1
        assert p3 >= p3

    def test_sorting(self):
        items = [PercentData("0.10"), PercentData("0.01"), PercentData("0.05")]
        assert sorted(items) == [
            PercentData("0.01"),
            PercentData("0.05"),
            PercentData("0.10"),
        ]

    def test_arithmetic(self):
        p = PercentData("0.10")
        result = p * Decimal("100")
        assert result == Decimal("10.0")

    def test_repr(self):
        p = PercentData("0.015")
        assert "0.015" in repr(p)

    def test_str(self):
        p = PercentData("0.015")
        assert str(p) == "1.50%"

    def test_immutable(self):
        p = PercentData("0.015")
        with pytest.raises(AttributeError):
            p.value = Decimal("0.020")  # type: ignore[misc]

    def test_eq_with_non_percent_returns_not_implemented(self):
        """Equality with non-PercentData returns NotImplemented (then False)."""
        p = PercentData("0.015")
        assert p != 0.015
        assert p != "0.015"

    def test_lt_with_non_percent_returns_not_implemented(self):
        """Less-than with non-PercentData raises TypeError."""
        p = PercentData("0.015")
        with pytest.raises(TypeError):
            _ = p < 0.5  # type: ignore[operator]

    def test_rmul(self):
        """Reverse multiplication: Decimal * PercentData."""
        p = PercentData("0.10")
        result = Decimal("200") * p
        assert result == Decimal("20.0")
