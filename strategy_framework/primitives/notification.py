"""ExecutorNotification — callback data from executors to orchestrator."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ExecutorNotification(BaseModel):
    """Immutable notification emitted by an executor on state change."""

    model_config = ConfigDict(frozen=True)

    executor_id: str
    controller_id: str
    event: str  # "started" | "completed" | "stopped" | "failed"
    data: dict[str, Any] = {}
