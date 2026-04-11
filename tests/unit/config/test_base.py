"""Tests for StrategyConfigBase."""

from decimal import Decimal

import pytest

from strategy_framework.config.base import StrategyConfigBase


class TestStrategyConfigBase:
    def test_creation(self):
        class MyConfig(StrategyConfigBase):
            controller_name: str = "test"
            controller_type: str = "directional_trading"
            amount: Decimal = Decimal("100")

        config = MyConfig(controller_id="ctrl_1")
        assert config.controller_id == "ctrl_1"
        assert config.controller_name == "test"

    def test_updatable_fields(self):
        class MyConfig(StrategyConfigBase):
            controller_name: str = "test"
            controller_type: str = "directional_trading"
            amount: Decimal = Decimal("100")

            class Meta:
                updatable = ["amount"]

        config = MyConfig(controller_id="ctrl_1")
        assert config.get_updatable_fields() == ["amount"]

    def test_update_from(self):
        class MyConfig(StrategyConfigBase):
            controller_name: str = "test"
            controller_type: str = "directional_trading"
            amount: Decimal = Decimal("100")

            class Meta:
                updatable = ["amount"]

        config = MyConfig(controller_id="ctrl_1")
        new_config = MyConfig(controller_id="ctrl_1", amount=Decimal("200"))
        config.update_from(new_config)
        assert config.amount == Decimal("200")

    def test_update_from_ignores_non_updatable(self):
        class MyConfig(StrategyConfigBase):
            controller_name: str = "test"
            controller_type: str = "directional_trading"
            amount: Decimal = Decimal("100")

            class Meta:
                updatable = ["amount"]

        config = MyConfig(controller_id="ctrl_1")
        new_config = MyConfig(
            controller_id="ctrl_1",
            controller_name="changed",
            amount=Decimal("200"),
        )
        config.update_from(new_config)
        assert config.controller_name == "test"  # unchanged
        assert config.amount == Decimal("200")  # updated

    def test_controller_id_required(self):
        from pydantic import ValidationError

        class MyConfig(StrategyConfigBase):
            controller_name: str = "test"
            controller_type: str = "directional_trading"

        with pytest.raises(ValidationError):
            MyConfig()  # type: ignore[call-arg]
