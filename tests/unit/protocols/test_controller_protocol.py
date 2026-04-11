"""Tests for ControllerProtocol."""

from strategy_framework.primitives.actions import CreateExecutorAction
from strategy_framework.protocols.controller import ControllerProtocol


class TestControllerProtocol:
    def test_is_runtime_checkable(self):
        assert not isinstance(object(), ControllerProtocol)

    def test_concrete_satisfies(self):
        class FakeController:
            @property
            def controller_id(self) -> str:
                return "ctrl_1"

            @property
            def processed_data(self) -> dict:
                return {"signal": 0}

            def determine_executor_actions(self) -> list:
                return [
                    CreateExecutorAction(
                        controller_id="ctrl_1",
                        executor_config={"type": "position"},
                    )
                ]

            async def update_processed_data(self) -> None:
                pass

        assert isinstance(FakeController(), ControllerProtocol)
