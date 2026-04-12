"""Tests for BalanceValidationMixin."""

from __future__ import annotations

from decimal import Decimal

import pytest

from strategy_framework.mixins.executor.balance import BalanceValidationMixin


class ConcreteBalance(BalanceValidationMixin):
    pass


def test_validate_balance_raises_not_implemented() -> None:
    obj = ConcreteBalance()
    with pytest.raises(NotImplementedError):
        obj.validate_balance("USDT", Decimal("1000"))


def test_not_implemented_message_mentions_adapter() -> None:
    obj = ConcreteBalance()
    with pytest.raises(NotImplementedError, match="get_available_balance"):
        obj.validate_balance("USDT", Decimal("1000"))


def test_not_implemented_message_mentions_market_simulator() -> None:
    obj = ConcreteBalance()
    with pytest.raises(NotImplementedError, match="market-simulator"):
        obj.validate_balance("BTC", Decimal("0.1"))

