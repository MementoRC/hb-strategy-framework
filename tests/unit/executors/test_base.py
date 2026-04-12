from __future__ import annotations

import pytest
from strategy_framework.executors.base import ExecutorState, ExecutorStateError


class TestExecutorState:
    def test_states_exist(self) -> None:
        assert ExecutorState.IDLE
        assert ExecutorState.ACTIVE
        assert ExecutorState.CLOSING
        assert ExecutorState.CLOSED

    def test_state_error_is_exception(self) -> None:
        err = ExecutorStateError("bad transition")
        assert isinstance(err, Exception)
        assert "bad transition" in str(err)
