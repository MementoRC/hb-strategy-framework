"""Spec builders and a small simulator driving the pure state machine."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from data_type_primitives import (
    LegRole,
    LegSpec,
    LinkedOrderSpec,
    LinkKind,
    OrderState,
    OrderType,
    TradeType,
    TriggerKind,
    TriggerSpec,
)

from strategy_framework.linked_orders.state import (
    CancelLeg,
    Delete,
    Emit,
    GetLeg,
    apply_cancel_outcome,
    apply_fill,
    apply_snapshot,
    apply_update,
    begin_leg,
    leg_placed,
    leg_rejected,
    leg_unknown,
    new_group,
    request_cancel,
    tick,
)
from strategy_framework.linked_orders.types import LegFill, LegSnapshot
from tests.unit.linked_orders.invariants import violations

if TYPE_CHECKING:
    from strategy_framework.linked_orders.events import LinkedEventKind
    from strategy_framework.linked_orders.state import Action, Transition
    from strategy_framework.linked_orders.types import (
        CancelOutcome,
        GroupRecord,
        LegRecord,
        LegStatus,
    )

D = Decimal


def _stop(price: str = "90") -> TriggerSpec:
    return TriggerSpec(kind=TriggerKind.ABSOLUTE, value=D(price))


def oco_spec(legs: int = 2) -> LinkedOrderSpec:
    specs = [
        LegSpec(
            role=LegRole.OCO_LEG,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            amount=D(1),
            price=D(110),
        ),
        LegSpec(
            role=LegRole.OCO_LEG,
            order_type=OrderType.STOP_LOSS,
            trade_type=TradeType.SELL,
            amount=D(1),
            trigger=_stop(),
        ),
        LegSpec(
            role=LegRole.OCO_LEG,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            amount=D(1),
            price=D(120),
        ),
    ]
    return LinkedOrderSpec(kind=LinkKind.OCO, legs=tuple(specs[:legs]))


def bracket_spec(*, take_profit: bool = True, stop_loss: bool = True) -> LinkedOrderSpec:
    legs = [
        LegSpec(
            role=LegRole.ENTRY,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=D(2),
            price=D(100),
        )
    ]
    if take_profit:
        legs.append(
            LegSpec(
                role=LegRole.TAKE_PROFIT,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.SELL,
                amount=D(2),
                price=D(110),
            )
        )
    if stop_loss:
        legs.append(
            LegSpec(
                role=LegRole.STOP_LOSS,
                order_type=OrderType.STOP_LOSS,
                trade_type=TradeType.SELL,
                amount=D(2),
                trigger=_stop(),
            )
        )
    return LinkedOrderSpec(kind=LinkKind.BRACKET, legs=tuple(legs))


class Sim:
    """Drives the pure functions and checks I1-I8 after every step. Leg i has id `c<i>`."""

    def __init__(self, spec: LinkedOrderSpec, *, now: float = 100.0, group_id: int = 1) -> None:
        self.spec = spec
        self.now = now
        self.rec: GroupRecord = new_group(group_id, "BTC-USD", spec, now)
        self.closed = False
        self.last: tuple[Action, ...] = ()
        self.log: list[Action] = []

    def _apply(self, trans: Transition) -> Sim:
        bad = violations(self.rec, trans, closed=self.closed)
        assert not bad, bad
        self.rec, self.last = trans.record, trans.actions
        self.log.extend(trans.actions)
        if any(isinstance(a, Delete) for a in trans.actions):
            self.closed = True
        return self

    # -- placement

    def begin(self, i: int) -> Sim:
        return self._apply(begin_leg(self.rec, i, f"t{i}", self.now))

    def reply(self, i: int, mode: str = "ok") -> Sim:
        if mode == "ok":
            return self._apply(leg_placed(self.rec, i, f"c{i}", self.now, closed=self.closed))
        if mode == "unknown":
            return self._apply(leg_unknown(self.rec, i, f"c{i}", self.now, closed=self.closed))
        return self._apply(leg_rejected(self.rec, i, self.now, closed=self.closed))

    def place(self, i: int, mode: str = "ok") -> Sim:
        return self.begin(i).reply(i, mode)

    def place_all(self) -> Sim:
        count = len(self.spec.legs) if self.spec.kind is LinkKind.OCO else 1
        for i in range(count):
            self.place(i)
        return self

    def place_exits(self) -> Sim:
        for i in range(1, len(self.spec.legs)):
            self.place(i)
        return self

    # -- inputs

    def update(self, i: int, state: OrderState) -> Sim:
        t = apply_update(self.rec, f"c{i}", state, self.now, closed=self.closed)
        return self._apply(t)

    def fill(self, i: int, cumulative: int | str) -> Sim:
        fill = LegFill(f"c{i}", D(str(cumulative)), D(100), self.now)
        return self._apply(apply_fill(self.rec, fill, self.now, closed=self.closed))

    def snap(self, i: int, state: OrderState | None, filled: int | str = 0) -> Sim:
        snapshot = None if state is None else LegSnapshot(f"c{i}", None, state, D(str(filled)))
        return self._apply(apply_snapshot(self.rec, i, snapshot, self.now, closed=self.closed))

    def cancel_out(self, i: int, outcome: CancelOutcome) -> Sim:
        t = apply_cancel_outcome(self.rec, i, outcome, self.now, closed=self.closed)
        return self._apply(t)

    def cancel(self) -> Sim:
        return self._apply(request_cancel(self.rec, self.now, closed=self.closed))

    def tick(self, dt: float = 0.0, grace: float = 30.0) -> Sim:
        self.now += dt
        if self.closed:
            return self
        return self._apply(tick(self.rec, self.now, grace))

    # -- views

    def leg(self, i: int) -> LegRecord:
        return self.rec.legs[i]

    def status(self, i: int) -> LegStatus:
        return self.rec.legs[i].status

    @property
    def cancels(self) -> list[int]:
        return [a.leg_index for a in self.last if isinstance(a, CancelLeg)]

    @property
    def get_legs(self) -> list[int]:
        return [a.leg_index for a in self.last if isinstance(a, GetLeg)]

    @property
    def kinds(self) -> list[LinkedEventKind]:
        return [a.event.kind for a in self.last if isinstance(a, Emit)]

    def events(self, kind: LinkedEventKind) -> list[object]:
        return [a.event for a in self.log if isinstance(a, Emit) and a.event.kind is kind]

    @property
    def deleted(self) -> bool:
        return any(isinstance(a, Delete) for a in self.log)
