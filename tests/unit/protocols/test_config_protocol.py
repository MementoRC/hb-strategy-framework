"""Tests for ConfigProtocol and UpdatableConfigProtocol."""

from strategy_framework.protocols.config import ConfigProtocol, UpdatableConfigProtocol


class TestConfigProtocol:
    def test_is_runtime_checkable(self):
        assert not isinstance(object(), ConfigProtocol)

    def test_concrete_satisfies(self):
        class FakeConfig:
            @property
            def controller_id(self) -> str:
                return "ctrl_1"

            @property
            def controller_name(self) -> str:
                return "my_strategy"

            @property
            def controller_type(self) -> str:
                return "directional_trading"

        assert isinstance(FakeConfig(), ConfigProtocol)


class TestUpdatableConfigProtocol:
    def test_concrete_satisfies(self):
        class FakeUpdatable:
            @property
            def controller_id(self) -> str:
                return "ctrl_1"

            @property
            def controller_name(self) -> str:
                return "my_strategy"

            @property
            def controller_type(self) -> str:
                return "directional_trading"

            def get_updatable_fields(self) -> list[str]:
                return ["total_amount_quote"]

            def update_from(self, other: object) -> None:
                pass

        assert isinstance(FakeUpdatable(), UpdatableConfigProtocol)
