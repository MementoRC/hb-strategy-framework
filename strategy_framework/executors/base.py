from __future__ import annotations

from enum import Enum, auto


class ExecutorState(Enum):
    IDLE = auto()
    ACTIVE = auto()
    CLOSING = auto()
    CLOSED = auto()


class ExecutorStateError(Exception):
    """Raised when an invalid state transition is attempted."""
