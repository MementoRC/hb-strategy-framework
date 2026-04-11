"""Executor action types — commands from controllers to the orchestrator."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class _ExecutorAction(BaseModel):
    """Base for all executor actions."""

    model_config = ConfigDict(frozen=True)

    controller_id: str
    action_type: str


class CreateExecutorAction(_ExecutorAction):
    """Command to create a new executor."""

    action_type: str = "create"
    executor_config: dict[str, Any]


class StopExecutorAction(_ExecutorAction):
    """Command to stop an existing executor."""

    action_type: str = "stop"
    executor_id: str
    keep_position: bool = False


class UpdateExecutorAction(_ExecutorAction):
    """Command to update a running executor's parameters."""

    action_type: str = "update"
    executor_id: str
    update_data: dict[str, Any]


class StoreExecutorAction(_ExecutorAction):
    """Command to archive an executor's state."""

    action_type: str = "store"
    executor_id: str
