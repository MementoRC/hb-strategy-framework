"""ExecutorProtocol — contract for executor implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from decimal import Decimal

    from strategy_framework.primitives.enums import CloseType, RunnableStatus


@runtime_checkable
class ExecutorProtocol(Protocol):
    """Contract that all executors must satisfy."""

    close_type: CloseType | None
    status: RunnableStatus

    def place_order(
        self,
        order_type: str,
        side: str,
        amount: Decimal,
        price: Decimal,
    ) -> str: ...

    def cancel_order(self, order_id: str) -> None: ...

    @property
    def net_pnl_pct(self) -> Decimal: ...

    @property
    def net_pnl_quote(self) -> Decimal: ...

    @property
    def is_done(self) -> bool: ...

    def early_stop(self, keep_position: bool = False) -> None: ...

    def update_live(self, update_data: dict[str, Any]) -> None: ...
