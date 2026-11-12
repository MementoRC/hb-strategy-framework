"""Core enums for the strategy framework."""

from enum import StrEnum

from data_type_primitives.common import OrderType as CanonicalOrderType
from data_type_primitives.common import TradeType as CanonicalTradeType


class CloseType(StrEnum):
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


class TradeType(StrEnum):
    """Buy or sell.

    String-serialized for pydantic/config compatibility; map to the canonical
    int-valued ``data_type_primitives`` enums via ``to_canonical``/``from_canonical``.
    """

    BUY = "buy"
    SELL = "sell"

    @property
    def opposite(self) -> "TradeType":
        return TradeType.SELL if self == TradeType.BUY else TradeType.BUY

    def to_canonical(self) -> CanonicalTradeType:
        """Map to the canonical ``data_type_primitives`` enum member."""
        return CanonicalTradeType[self.name]

    @classmethod
    def from_canonical(cls, value: CanonicalTradeType) -> "TradeType":
        """Build from a canonical ``data_type_primitives`` enum member."""
        return cls[value.name]


class OrderType(StrEnum):
    """Order type for placement.

    String-serialized for pydantic/config compatibility; map to the canonical
    int-valued ``data_type_primitives`` enums via ``to_canonical``/``from_canonical``.
    """

    LIMIT = "limit"
    MARKET = "market"
    LIMIT_MAKER = "limit_maker"

    def to_canonical(self) -> CanonicalOrderType:
        """Map to the canonical ``data_type_primitives`` enum member."""
        return CanonicalOrderType[self.name]

    @classmethod
    def from_canonical(cls, value: CanonicalOrderType) -> "OrderType":
        """Build from a canonical ``data_type_primitives`` enum member.

        Only ``MARKET``, ``LIMIT``, and ``LIMIT_MAKER`` are representable;
        other canonical members (AMM/conditional order types) have no
        equivalent here and raise ``KeyError``.
        """
        return cls[value.name]


class RunnableStatus(StrEnum):
    """Lifecycle status of a runnable (executor or controller)."""

    NOT_STARTED = "not_started"
    RUNNING = "running"
    SHUTTING_DOWN = "shutting_down"
    TERMINATED = "terminated"

    @property
    def is_active(self) -> bool:
        return self in {RunnableStatus.RUNNING, RunnableStatus.SHUTTING_DOWN}
