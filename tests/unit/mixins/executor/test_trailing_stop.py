"""Tests for TrailingStopMixin."""

from __future__ import annotations

from decimal import Decimal

from strategy_framework.mixins.executor.trailing_stop import TrailingStopMixin
from strategy_framework.primitives.enums import CloseType, RunnableStatus
from strategy_framework.primitives.trailing_stop import TrailingStop
from strategy_framework.primitives.triple_barrier import TripleBarrierConfig


class ConcreteTrailing(TrailingStopMixin):
    """Concrete executor with controllable PnL and trailing stop config."""

    def __init__(
        self,
        trailing_stop: TrailingStop | None,
        initial_pnl_pct: Decimal = Decimal("0"),
    ) -> None:
        self._trailing_stop_cfg = trailing_stop
        self._pnl_pct = initial_pnl_pct
        self.status = RunnableStatus.RUNNING
        self.close_type: CloseType | None = None
        self.elapsed_seconds: float = 0.0
        self._init_trailing_stop()

    @property
    def net_pnl_pct(self) -> Decimal:
        return self._pnl_pct

    @property
    def trailing_stop(self) -> TrailingStop | None:
        return self._trailing_stop_cfg

    @property
    def triple_barrier(self) -> TripleBarrierConfig:
        return TripleBarrierConfig(stop_loss=Decimal("0.05"), take_profit=Decimal("0.1"))

    def place_close_order(self, close_type: CloseType) -> None:
        self.close_type = close_type


TS_CONFIG = TrailingStop(
    activation_price_pct=Decimal("0.02"),  # activates at +2% PnL
    trailing_delta_pct=Decimal("0.01"),  # trigger = pnl - 1%
)


def test_init_state() -> None:
    obj = ConcreteTrailing(TS_CONFIG)
    assert obj.trailing_stop_activated is False
    assert obj.trailing_stop_triggered is False


def test_not_triggered_without_config() -> None:
    obj = ConcreteTrailing(None)
    obj.update_trailing_stop(Decimal("105"))
    assert obj.trailing_stop_triggered is False


def test_not_activated_below_threshold() -> None:
    obj = ConcreteTrailing(TS_CONFIG, initial_pnl_pct=Decimal("0.01"))  # below 0.02
    obj.update_trailing_stop(Decimal("101"))
    assert obj.trailing_stop_activated is False


def test_activates_at_threshold() -> None:
    obj = ConcreteTrailing(TS_CONFIG, initial_pnl_pct=Decimal("0.02"))  # exactly 0.02
    obj.update_trailing_stop(Decimal("102"))
    assert obj.trailing_stop_activated is True


def test_not_triggered_immediately_after_activation() -> None:
    obj = ConcreteTrailing(TS_CONFIG, initial_pnl_pct=Decimal("0.03"))
    obj.update_trailing_stop(Decimal("103"))
    assert obj.trailing_stop_activated is True
    assert obj.trailing_stop_triggered is False


def test_ratchet_advances_trigger_on_higher_pnl() -> None:
    obj = ConcreteTrailing(TS_CONFIG, initial_pnl_pct=Decimal("0.02"))
    obj.update_trailing_stop(Decimal("102"))  # activates; trigger at 0.01
    obj._pnl_pct = Decimal("0.04")
    obj.update_trailing_stop(Decimal("104"))  # ratchet; trigger at 0.03
    # PnL drops to 0.031 — above trigger (0.03), not triggered
    obj._pnl_pct = Decimal("0.031")
    obj.update_trailing_stop(Decimal("103.1"))
    assert obj.trailing_stop_triggered is False
    # PnL drops below trigger
    obj._pnl_pct = Decimal("0.02")
    obj.update_trailing_stop(Decimal("102"))
    assert obj.trailing_stop_triggered is True


def test_triggered_when_pnl_drops_below_trigger() -> None:
    obj = ConcreteTrailing(TS_CONFIG, initial_pnl_pct=Decimal("0.02"))
    obj.update_trailing_stop(Decimal("102"))  # activates; trigger=0.01
    obj._pnl_pct = Decimal("0.005")  # below trigger
    obj.update_trailing_stop(Decimal("100.5"))
    assert obj.trailing_stop_triggered is True


def test_init_trailing_stop_resets_state() -> None:
    obj = ConcreteTrailing(TS_CONFIG, initial_pnl_pct=Decimal("0.05"))
    obj.update_trailing_stop(Decimal("105"))
    obj._init_trailing_stop()
    assert obj.trailing_stop_activated is False
    assert obj.trailing_stop_triggered is False
