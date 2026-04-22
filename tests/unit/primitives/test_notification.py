"""Tests for ExecutorNotification primitive."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from strategy_framework.primitives.notification import ExecutorNotification


def test_notification_creation():
    n = ExecutorNotification(
        executor_id="exec-1",
        controller_id="ctrl-1",
        event="completed",
    )
    assert n.executor_id == "exec-1"
    assert n.controller_id == "ctrl-1"
    assert n.event == "completed"
    assert n.data == {}


def test_notification_with_data():
    n = ExecutorNotification(
        executor_id="exec-1",
        controller_id="ctrl-1",
        event="failed",
        data={"reason": "timeout"},
    )
    assert n.data == {"reason": "timeout"}


def test_notification_is_frozen():
    n = ExecutorNotification(executor_id="e", controller_id="c", event="started")
    with pytest.raises(ValidationError):
        n.event = "changed"  # type: ignore[misc]
