"""Tests for the dtp v0.13 `LinkedCancelOutcome` contract: residual, status, leg_outcomes."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from data_type_primitives import (
    LegRole,
    LegSpec,
    LinkedCancelStatus,
    LinkedOrderSpec,
    LinkKind,
    OrderState,
    OrderType,
    TradeType,
)

from strategy_framework.linked_orders.state import (
    cancel_status,
    is_terminal,
    leg_cancel_outcomes,
    residual_filled,
)
from strategy_framework.linked_orders.types import (
    CancelOutcome,
    GroupRecord,
    GroupState,
    LegRecord,
    LegStatus,
    LinkedCancelOutcome,
)
from tests.unit.linked_orders.builders import Sim, bracket_spec, oco_spec

D = Decimal
OS = OrderState
CO = CancelOutcome
ST = LinkedCancelStatus


def build(rec: GroupRecord) -> LinkedCancelOutcome:
    """Mirror of `cancel_linked`'s construction; the dtp validator runs on construction."""
    terminal = len(rec.legs) == len(rec.spec.legs) and all(is_terminal(x) for x in rec.legs)
    return LinkedCancelOutcome(
        group_id=str(rec.group_id),
        state=rec.state,
        all_legs_terminal=terminal,
        residual_filled=residual_filled(rec),
        leg_outcomes=leg_cancel_outcomes(rec),
        status=cancel_status(rec.state, all_legs_terminal=terminal),
    )


def bracket_with_exits(entry_fill: str) -> Sim:
    """BRACKET whose entry filled `entry_fill`, was closed out, and whose exits are placed."""
    sim = Sim(bracket_spec()).place_all().fill(0, entry_fill).update(0, OS.CANCELED)
    return sim.snap(0, OS.CANCELED, entry_fill).place_exits()


# --------------------------------------------------------------------------- residual


def test_residual_bracket_entry_and_tp_fully_filled_is_zero() -> None:
    sim = bracket_with_exits("1").fill(1, 1)
    assert residual_filled(sim.rec) == 0
    build(sim.rec)


def test_residual_bracket_tp_partial_then_cancel() -> None:
    sim = bracket_with_exits("1").fill(1, "0.4").cancel()
    assert residual_filled(sim.rec) == D("0.6")
    build(sim.rec)


def test_residual_bracket_entry_cancelled_before_exits() -> None:
    sim = Sim(bracket_spec()).place_all().fill(0, "0.5").cancel().cancel_out(0, CO.CANCELED)
    sim.snap(0, OS.CANCELED, "0.5")
    assert sim.rec.state is GroupState.CANCELED
    assert residual_filled(sim.rec) == D("0.5")


def test_residual_bracket_double_fill_is_negative() -> None:
    sim = bracket_with_exits("1").fill(1, 1).fill(2, 1)
    assert residual_filled(sim.rec) == -1
    build(sim.rec)


def test_residual_same_side_oco_sums_fills() -> None:
    sim = Sim(oco_spec()).place_all().fill(0, "0.5").fill(1, "0.25")
    assert residual_filled(sim.rec) == D("0.75")


def test_residual_opposite_side_oco_double_fill_nets_zero() -> None:
    def leg_spec(trade_type: TradeType) -> LegSpec:
        return LegSpec(
            role=LegRole.OCO_LEG,
            order_type=OrderType.LIMIT,
            trade_type=trade_type,
            amount=D(1),
            price=D(100),
        )

    # dtp's OCO validator requires one side; a breakout pair is built unvalidated.
    spec = LinkedOrderSpec.model_construct(
        kind=LinkKind.OCO, legs=(leg_spec(TradeType.BUY), leg_spec(TradeType.SELL))
    )
    legs = tuple(
        LegRecord(i, LegRole.OCO_LEG, f"t{i}", f"c{i}", LegStatus.FILLED, D(1), D(1))
        for i in range(2)
    )
    rec = GroupRecord(1, "BTC-USD", spec, GroupState.DEGRADED, legs)
    assert residual_filled(rec) == 0
    assert build(rec).status is ST.UNKNOWN


def test_residual_oco_without_fill_is_zero() -> None:
    sim = Sim(oco_spec()).place_all().cancel()
    assert residual_filled(sim.rec) == 0


# --------------------------------------------------------------------------- status


def test_status_user_cancel_is_canceled() -> None:
    sim = Sim(oco_spec()).place_all().cancel().cancel_out(0, CO.CANCELED).cancel_out(1, CO.CANCELED)
    out = build(sim.rec)
    assert out.status is ST.CANCELED
    assert out.all_legs_terminal is True


def test_status_rollback_is_failed() -> None:
    sim = Sim(oco_spec()).place(0).place(1, "reject")
    assert sim.rec.cancel_cause == "rollback"
    sim.cancel_out(0, CO.CANCELED)
    out = build(sim.rec)
    assert out.state is GroupState.FAILED
    assert out.status is ST.FAILED


def test_status_cancelling_with_unresolved_leg_is_unknown() -> None:
    sim = Sim(oco_spec()).place_all().cancel()
    legs = tuple(replace(x, status=LegStatus.CANCELED, unresolved_since=1.0) for x in sim.rec.legs)
    rec = replace(sim.rec, legs=legs)
    assert rec.state is GroupState.CANCELLING
    out = build(rec)
    assert out.all_legs_terminal is True
    assert out.status is ST.UNKNOWN


def test_status_cancelling_with_open_legs_is_pending() -> None:
    out = build(Sim(oco_spec()).place_all().cancel().rec)
    assert out.all_legs_terminal is False
    assert out.status is ST.PENDING


def test_status_completed_with_partial_winner_is_filled_not_terminal() -> None:
    sim = Sim(oco_spec()).place_all().fill(0, "0.5").cancel_out(1, CO.CANCELED)
    assert sim.rec.state is GroupState.COMPLETED
    assert sim.status(0) is LegStatus.PARTIALLY_FILLED
    out = build(sim.rec)
    assert out.all_legs_terminal is False
    assert out.status is ST.FILLED


def test_cancel_status_table() -> None:
    terminal = {
        GroupState.CANCELED: ST.CANCELED,
        GroupState.FAILED: ST.FAILED,
        GroupState.COMPLETED: ST.FILLED,
        GroupState.DEGRADED: ST.UNKNOWN,
        GroupState.CANCELLING: ST.UNKNOWN,
        GroupState.ARMED: ST.UNKNOWN,
    }
    for state, expected in terminal.items():
        assert cancel_status(state, all_legs_terminal=True) is expected
    open_legs = {
        GroupState.CANCELLING: ST.PENDING,
        GroupState.COMPLETED: ST.FILLED,
        GroupState.DEGRADED: ST.UNKNOWN,
        GroupState.CANCELED: ST.UNKNOWN,
        GroupState.FAILED: ST.UNKNOWN,
        GroupState.ARMED: ST.UNKNOWN,
    }
    for state, expected in open_legs.items():
        assert cancel_status(state, all_legs_terminal=False) is expected


# --------------------------------------------------------------------------- leg_outcomes


def test_single_exit_bracket_cancel_has_one_outcome_per_spec_leg() -> None:
    spec = bracket_spec(stop_loss=False)
    sim = Sim(spec).place_all().cancel().cancel_out(0, CO.CANCELED)
    out = build(sim.rec)
    assert len(out.leg_outcomes) == len(spec.legs) == 2
    assert out.leg_outcomes == (CO.CANCELED, None)


def test_sealed_not_placed_legs_are_none() -> None:
    sim = Sim(bracket_spec()).place_all().cancel().cancel_out(0, CO.CANCELED)
    assert [x.status for x in sim.rec.legs[1:]] == [LegStatus.NOT_PLACED] * 2
    assert build(sim.rec).leg_outcomes == (CO.CANCELED, None, None)


def test_submitted_filled_winner_is_already_filled() -> None:
    sim = Sim(oco_spec()).place_all().fill(0, 1)
    assert leg_cancel_outcomes(sim.rec) == (CO.ALREADY_FILLED, CO.UNKNOWN)
    sim.cancel_out(1, CO.CANCELED)
    out = build(sim.rec)
    assert out.leg_outcomes == (CO.ALREADY_FILLED, CO.CANCELED)
    assert sim.rec.legs[0].cancel_outcome is None  # the record is not mutated


def test_rejected_leg_without_client_id_is_none() -> None:
    sim = Sim(oco_spec()).place(0).place(1, "reject")
    assert leg_cancel_outcomes(sim.rec)[1] is None
