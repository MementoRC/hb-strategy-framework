"""PercentData — hashable, comparable, quantized Decimal wrapper for percentages."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from functools import total_ordering

_QUANTIZE_EXP = Decimal("0.000001")  # 6 decimal places


@total_ordering
class PercentData:
    """Immutable, hashable percentage value.

    Used as dict keys in order management (e.g., trailing stop levels).
    Stored as a Decimal fraction (0.015 = 1.5%).
    """

    __slots__ = ("_value",)

    def __init__(self, value: str | float | Decimal) -> None:
        if isinstance(value, float):
            value = Decimal(str(value))
        elif isinstance(value, str):
            value = Decimal(value)
        object.__setattr__(self, "_value", value.quantize(_QUANTIZE_EXP, rounding=ROUND_HALF_UP))

    def _get_value(self) -> Decimal:
        result: Decimal = object.__getattribute__(self, "_value")
        return result

    @property
    def value(self) -> Decimal:
        return self._get_value()

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(f"{type(self).__name__} is immutable")

    def __hash__(self) -> int:
        return hash(self._get_value())

    def __eq__(self, other: object) -> bool:
        if isinstance(other, PercentData):
            return self._get_value() == other._get_value()
        return NotImplemented

    def __lt__(self, other: object) -> bool:
        if isinstance(other, PercentData):
            return self._get_value() < other._get_value()
        return NotImplemented

    def __mul__(self, other: Decimal) -> Decimal:
        return self._get_value() * other

    def __rmul__(self, other: Decimal) -> Decimal:
        return other * self._get_value()

    def __repr__(self) -> str:
        return f"PercentData({self._get_value()})"

    def __str__(self) -> str:
        pct = self._get_value() * 100
        return f"{pct:.2f}%"
