"""Core enums for the strategy framework."""

from enum import Enum


class CloseType(str, Enum):
    """Reason an executor closed its position."""

    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TIME_LIMIT = "time_limit"
    TRAILING_STOP = "trailing_stop"
    EARLY_STOP = "early_stop"
    EXPIRED = "expired"
    FAILED = "failed"

    @property
    def is_terminal(self) -> bool:
        """Whether this close type means the executor is fully done."""
        return self in {
            CloseType.STOP_LOSS,
            CloseType.TAKE_PROFIT,
            CloseType.TIME_LIMIT,
            CloseType.EARLY_STOP,
            CloseType.EXPIRED,
            CloseType.FAILED,
        }


class TradeType(str, Enum):
    """Buy or sell."""

    BUY = "buy"
    SELL = "sell"

    @property
    def opposite(self) -> "TradeType":
        return TradeType.SELL if self == TradeType.BUY else TradeType.BUY


class OrderType(str, Enum):
    """Order type for placement."""

    LIMIT = "limit"
    MARKET = "market"
    LIMIT_MAKER = "limit_maker"


class RunnableStatus(str, Enum):
    """Lifecycle status of a runnable (executor or controller)."""

    NOT_STARTED = "not_started"
    RUNNING = "running"
    SHUTTING_DOWN = "shutting_down"
    TERMINATED = "terminated"

    @property
    def is_active(self) -> bool:
        return self in {RunnableStatus.RUNNING, RunnableStatus.SHUTTING_DOWN}
