"""Tests for ActivationBoundsMixin."""

from __future__ import annotations

from decimal import Decimal

from strategy_framework.mixins.executor.activation import ActivationBoundsMixin
from strategy_framework.protocols.composites import ActivationBoundsProtocol


class ConcreteActivation(ActivationBoundsMixin):
    def __init__(
        self,
        entry_price: Decimal,
        activation_bounds: tuple[Decimal, Decimal] | None,
    ) -> None:
        self.entry_price = entry_price
        self.activation_bounds = activation_bounds


ENTRY = Decimal("100")
BOUNDS = (Decimal("0.99"), Decimal("1.01"))  # ±1%


def test_none_bounds_always_active() -> None:
    obj = ConcreteActivation(ENTRY, None)
    assert obj.is_within_activation_bounds(Decimal("50")) is True
    assert obj.is_within_activation_bounds(Decimal("200")) is True


def test_within_bounds_lower_edge() -> None:
    obj = ConcreteActivation(ENTRY, BOUNDS)
    assert obj.is_within_activation_bounds(Decimal("99")) is True


def test_within_bounds_upper_edge() -> None:
    obj = ConcreteActivation(ENTRY, BOUNDS)
    assert obj.is_within_activation_bounds(Decimal("101")) is True


def test_below_lower_bound() -> None:
    obj = ConcreteActivation(ENTRY, BOUNDS)
    assert obj.is_within_activation_bounds(Decimal("98.99")) is False


def test_above_upper_bound() -> None:
    obj = ConcreteActivation(ENTRY, BOUNDS)
    assert obj.is_within_activation_bounds(Decimal("101.01")) is False


def test_at_entry_price() -> None:
    obj = ConcreteActivation(ENTRY, BOUNDS)
    assert obj.is_within_activation_bounds(ENTRY) is True


def test_tight_bounds() -> None:
    tight = (Decimal("1.0"), Decimal("1.0"))  # only exactly at entry
    obj = ConcreteActivation(ENTRY, tight)
    assert obj.is_within_activation_bounds(Decimal("100")) is True
    assert obj.is_within_activation_bounds(Decimal("100.01")) is False


def test_satisfies_activation_bounds_protocol() -> None:
    obj = ConcreteActivation(ENTRY, BOUNDS)
    assert isinstance(obj, ActivationBoundsProtocol)
