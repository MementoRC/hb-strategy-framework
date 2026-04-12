from __future__ import annotations

import pytest
from strategy_framework.executors.base import ExecutorState, ExecutorStateError


class TestExecutorState:
    def test_all_four_states_exist(self) -> None:
        members = {s.name for s in ExecutorState}
        assert members == {"IDLE", "ACTIVE", "CLOSING", "CLOSED"}

    def test_state_count(self) -> None:
        assert len(ExecutorState) == 4

    def test_state_error_is_exception(self) -> None:
        with pytest.raises(ExecutorStateError, match="bad transition"):
            raise ExecutorStateError("bad transition")
