"""TrailingStopMixin — PnL-based trailing stop ratchet algorithm.

Ported from hummingbot/strategy_v2/executors/mixins/trailing_stop.py.
Key adaptation: uses TrailingStop.activation_price_pct and trailing_delta_pct
(with _pct suffix) — NOT the in-tree names activation_price/trailing_delta.

Tracks PnL-percentage-based trigger (not price), reading net_pnl_pct from
BarrierControlProtocol.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from strategy_framework.protocols.composites import BarrierControlProtocol


class TrailingStopMixin:
    """Mixin providing the trailing stop ratchet algorithm.

    Algorithm:
    1. Wait until net_pnl_pct >= trailing_stop.activation_price_pct
    2. Set trigger = net_pnl_pct - trailing_delta_pct
    3. Ratchet trigger upward as PnL rises (trigger = max(trigger, pnl - delta))
    4. trailing_stop_triggered = True when pnl drops below trigger

    Usage:
        class MyExecutor(TrailingStopMixin):
            def __init__(self) -> None:
                self._init_trailing_stop()

            # host must provide via BarrierControlProtocol:
            #   net_pnl_pct: Decimal (property)
            #   trailing_stop: TrailingStop | None (property)
            #   status, close_type, triple_barrier, elapsed_seconds, place_close_order

            def _check_trailing_stop(self) -> None:
                self.update_trailing_stop(self.market.get_mid_price())
                if self.trailing_stop_triggered:
                    self.place_close_order(CloseType.TRAILING_STOP)

    SIDE EFFECT: update_trailing_stop() may advance the trigger floor.
    Call only once per price tick — do not call speculatively.

    MRO init order: call _init_trailing_stop() after all super().__init__() calls.
    Calling _init_trailing_stop() twice resets state (safe in diamond MRO).
    """

    def _init_trailing_stop(self: BarrierControlProtocol) -> None:  # type: ignore[misc]
        """Initialize trailing stop state. Call from __init__ after super().__init__()."""
        self._trailing_stop_trigger_pct: Decimal | None = None  # type: ignore[attr-defined]
        self._trailing_stop_activated: bool = False  # type: ignore[attr-defined]
        self._trailing_stop_triggered: bool = False  # type: ignore[attr-defined]

    def update_trailing_stop(
        self: BarrierControlProtocol,  # type: ignore[misc]
        current_price: Decimal,  # noqa: ARG002 — reserved for price-based future variant
    ) -> None:
        """Advance the trailing stop ratchet based on current PnL.

        SIDE EFFECT: may set _trailing_stop_trigger_pct and _trailing_stop_triggered.
        Call once per price tick only.

        current_price is accepted but unused — the algorithm is PnL-pct-based.
        Provided for API consistency; a future subclass may use price-based ratchet.
        """
        ts = self.trailing_stop
        if ts is None:
            return

        pnl_pct = self.net_pnl_pct

        if not self._trailing_stop_activated:  # type: ignore[attr-defined]
            if pnl_pct >= ts.activation_price_pct:
                self._trailing_stop_activated = True  # type: ignore[attr-defined]
                self._trailing_stop_trigger_pct = pnl_pct - ts.trailing_delta_pct  # type: ignore[attr-defined]
            return

        # Already activated — check fire condition
        if pnl_pct < self._trailing_stop_trigger_pct:  # type: ignore[operator]
            self._trailing_stop_triggered = True  # type: ignore[attr-defined]
            return

        # Ratchet: advance trigger floor if PnL has risen
        new_trigger = pnl_pct - ts.trailing_delta_pct
        if new_trigger > self._trailing_stop_trigger_pct:  # type: ignore[operator]
            self._trailing_stop_trigger_pct = new_trigger  # type: ignore[attr-defined]

    @property
    def trailing_stop_triggered(self: BarrierControlProtocol) -> bool:  # type: ignore[misc]
        """True if the trailing stop condition has been met."""
        return self._trailing_stop_triggered  # type: ignore[attr-defined]

    @property
    def trailing_stop_activated(self: BarrierControlProtocol) -> bool:  # type: ignore[misc]
        """True if activation threshold has been crossed (ratchet is live)."""
        return self._trailing_stop_activated  # type: ignore[attr-defined]
