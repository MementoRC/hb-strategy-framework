"""Pure state-table tests: one case per spec row 1-25 (I1-I8 are checked on every step)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from data_type_primitives import OrderState

from strategy_framework.linked_orders.events import LinkedEventKind as K
from strategy_framework.linked_orders.state import (
    CancelLeg,
    Persist,
    PlaceLeg,
    apply_fill,
    apply_update,
    begin_leg,
    can_place,
    make_handle,
    residual_filled,
)
from strategy_framework.linked_orders.types import (
    BracketHandle,
    CancelOutcome,
    DegradedReason,
    GroupState,
    LegFill,
    LegStatus,
    OcoHandle,
)
from tests.unit.linked_orders.builders import Sim, bracket_spec, oco_spec

D = Decimal
S = GroupState
LS = LegStatus
OS = OrderState


def _armed_oco(legs: int = 2) -> Sim:
    return Sim(oco_spec(legs)).place_all()


def _bracket_exits_placing(entry_fill: str = "2", *, tp: bool = True, sl: bool = True) -> Sim:
    sim = Sim(bracket_spec(take_profit=tp, stop_loss=sl)).place(0)
    sim.fill(0, entry_fill).update(0, OS.CANCELED if D(entry_fill) < 2 else OS.FILLED)
    return sim.snap(0, OS.CANCELED if D(entry_fill) < 2 else OS.FILLED, entry_fill)


# ---------------------------------------------------------------- rows 1-4


def test_row1_new_group_is_placing_and_write_ahead_first() -> None:
    sim = Sim(oco_spec())
    assert sim.rec.state is S.PLACING
    assert sim.rec.legs == ()
    sim.begin(0)
    assert sim.last == (Persist(), PlaceLeg(0))
    assert sim.leg(0).status is LS.PENDING_CREATE
    assert sim.leg(0).link_tag == "t0"


def test_row2_legs_are_submitted_in_order_only_while_placing() -> None:
    sim = Sim(oco_spec())
    with pytest.raises(ValueError, match="in order"):
        begin_leg(sim.rec, 1, "x", 0.0)
    sim.place(0).place(1)
    assert sim.rec.state is S.ARMED
    with pytest.raises(ValueError, match="cannot place"):
        begin_leg(sim.rec, 2, "x", 0.0)


def test_row2_bracket_places_entry_first_then_exits() -> None:
    sim = Sim(bracket_spec()).begin(0)
    with pytest.raises(ValueError, match="entry first"):
        begin_leg(sim.rec, 1, "x", 0.0)
    assert can_place(sim.rec)


def test_row3_oco_all_submitted_is_armed() -> None:
    sim = Sim(oco_spec())
    sim.place(0)
    assert sim.rec.state is S.PLACING
    sim.place(1)
    assert sim.rec.state is S.ARMED
    assert K.PLACED in sim.kinds
    handle = make_handle(sim.rec)
    assert isinstance(handle, OcoHandle)
    assert handle.leg_client_order_ids == ("c0", "c1")
    assert handle.state is S.ARMED
    assert handle.emulated is True


def test_row4_bracket_entry_submitted_is_entry_working() -> None:
    sim = Sim(bracket_spec()).begin(0)
    assert sim.rec.state is S.PLACING
    sim.reply(0)
    assert sim.rec.state is S.ENTRY_WORKING
    handle = make_handle(sim.rec)
    assert isinstance(handle, BracketHandle)
    assert handle.entry_client_order_id == "c0"
    assert handle.take_profit_client_order_id is None
    assert handle.stop_loss_client_order_id is None


# ---------------------------------------------------------------- rows 5-6


def test_row5_unknown_outcome_marks_leg_unresolved() -> None:
    sim = Sim(oco_spec()).place(0, "unknown")
    assert sim.status(0) is LS.UNKNOWN
    assert sim.leg(0).client_order_id == "c0"
    assert sim.leg(0).unresolved_since == sim.now


@pytest.mark.parametrize("via", ["snapshot", "update"])
def test_row6_resolving_report_clears_unresolved(via: str) -> None:
    sim = Sim(oco_spec()).place(0, "unknown").place(1)
    assert sim.rec.state is S.ARMED
    if via == "snapshot":
        sim.snap(0, OS.OPEN)
    else:
        sim.update(0, OS.OPEN)
    assert sim.status(0) is LS.OPEN
    assert sim.leg(0).unresolved_since is None


# ---------------------------------------------------------------- rows 7, 15


def test_row7_second_oco_leg_rejected_rolls_back_first() -> None:
    sim = Sim(oco_spec()).place(0).begin(1).reply(1, "reject")
    assert sim.rec.state is S.CANCELLING
    assert sim.rec.cancel_cause == "rollback"
    assert sim.cancels == [0]
    assert sim.status(1) is LS.FAILED
    sim.cancel_out(0, CancelOutcome.CANCELED)
    assert sim.rec.state is S.FAILED
    assert K.FAILED in sim.kinds
    assert sim.deleted


def test_row7_first_leg_rejected_fails_group_and_seals_rest() -> None:
    sim = Sim(oco_spec(3)).place(0, "reject")
    assert sim.rec.state is S.FAILED
    assert [leg.status for leg in sim.rec.legs] == [LS.FAILED, LS.NOT_PLACED, LS.NOT_PLACED]
    assert sim.deleted


def test_row7_rollback_waits_for_unresolved_leg() -> None:
    sim = Sim(oco_spec(3)).place(0, "unknown").place(1).begin(2).reply(2, "reject")
    assert sim.rec.state is S.CANCELLING
    assert sim.cancels == []
    sim.snap(0, OS.OPEN)
    assert sorted(sim.cancels) == [0, 1]
    assert sim.rec.cancel_cause == "rollback"


def test_row7_bracket_entry_rejected_fails_group() -> None:
    sim = Sim(bracket_spec()).place(0, "reject")
    assert sim.rec.state is S.FAILED


def test_row15_exit_rejected_degrades_without_retry() -> None:
    sim = _bracket_exits_placing()
    assert sim.rec.state is S.EXITS_PLACING
    sim.place(1).begin(2).reply(2, "reject")
    assert sim.rec.state is S.DEGRADED
    assert sim.rec.degraded_reasons == {DegradedReason.EXIT_PLACEMENT_FAILED}
    assert sim.status(1) is LS.OPEN
    assert sim.status(2) is LS.FAILED
    assert not can_place(sim.rec)
    handle = make_handle(sim.rec)
    assert isinstance(handle, BracketHandle)
    assert handle.take_profit_client_order_id == "c1"
    assert handle.stop_loss_client_order_id is None  # definitely rejected: no id


def test_row15_first_exit_rejected_seals_second_and_closes() -> None:
    sim = _bracket_exits_placing().begin(1).reply(1, "reject")
    assert sim.rec.state is S.DEGRADED
    assert sim.status(2) is LS.NOT_PLACED
    handle = make_handle(sim.rec)
    assert isinstance(handle, BracketHandle)
    assert handle.stop_loss_client_order_id is None
    assert sim.deleted


# ---------------------------------------------------------------- rows 8-10


def test_row8_full_fill_triggers_and_row9_cancels_siblings() -> None:
    sim = _armed_oco()
    sim.fill(0, 1)
    assert sim.rec.state is S.TRIGGERED
    assert sim.rec.winner_leg_index == 0
    assert sim.cancels == [1]
    trig = [e for e in sim.events(K.TRIGGERED)]
    assert len(trig) == 1
    assert trig[0].deferred is False  # type: ignore[attr-defined]


def test_row8_partial_fill_triggers_too() -> None:
    sim = _armed_oco()
    sim.fill(1, "0.1")
    assert sim.rec.state is S.TRIGGERED
    assert sim.rec.winner_leg_index == 1
    assert sim.cancels == [0]


def test_row8_trigger_during_placing_seals_unsubmitted_legs() -> None:
    sim = Sim(oco_spec(3)).place(0)
    sim.fill(0, 1)
    assert [leg.status for leg in sim.rec.legs] == [LS.FILLED, LS.NOT_PLACED, LS.NOT_PLACED]
    assert not can_place(sim.rec)
    with pytest.raises(ValueError, match="cannot place"):
        begin_leg(sim.rec, 1, "x", 0.0)
    assert sim.rec.state is S.COMPLETED
    assert sim.deleted
    handle = make_handle(sim.rec)
    assert isinstance(handle, OcoHandle)
    assert handle.leg_client_order_ids == ("c0", None, None)


def test_row8_trigger_while_reply_pending_defers_cancel() -> None:
    sim = Sim(oco_spec()).place(0).begin(1)
    sim.fill(0, 1)
    assert sim.rec.state is S.TRIGGERED
    assert sim.cancels == []
    assert sim.events(K.TRIGGERED)[0].deferred is True  # type: ignore[attr-defined]
    sim.reply(1)
    assert sim.cancels == [1]


def test_row9_deferred_cancel_issued_when_unknown_leg_resolves_open() -> None:
    sim = Sim(oco_spec()).place(0, "unknown").place(1)
    sim.fill(1, 1)
    assert sim.cancels == []
    assert sim.events(K.TRIGGERED)[0].deferred is True  # type: ignore[attr-defined]
    sim.snap(0, OS.OPEN)
    assert sim.cancels == [0]


def test_row10_non_winner_terminal_completes_and_winner_tracked_to_close() -> None:
    sim = _armed_oco()
    sim.fill(0, "0.4")
    sim.cancel_out(1, CancelOutcome.CANCELED)
    assert sim.rec.state is S.COMPLETED
    assert K.COMPLETED in sim.kinds
    assert not sim.deleted
    sim.fill(0, "0.7")
    assert sim.rec.state is S.COMPLETED
    assert len(sim.events(K.TRIGGERED)) == 1
    sim.fill(0, 1)
    assert sim.deleted
    assert K.CLOSED in sim.kinds


def test_row10_unknown_sibling_resolving_failed_completes() -> None:
    sim = Sim(oco_spec()).place(0, "unknown").place(1).fill(1, 1)
    sim.snap(0, OS.FAILED)
    assert sim.rec.state is S.COMPLETED


# ---------------------------------------------------------------- row 11 / 24 / 25


def test_row11_already_filled_cancel_outcome_is_double_fill() -> None:
    sim = _armed_oco().fill(0, 1)
    sim.cancel_out(1, CancelOutcome.ALREADY_FILLED)
    assert sim.rec.state is S.DEGRADED
    assert sim.rec.degraded_reasons == {DegradedReason.DOUBLE_FILL}
    ev = sim.events(K.DEGRADED)
    assert len(ev) == 1
    assert ev[0].client_order_ids == ("c0", "c1")  # type: ignore[attr-defined]
    assert ev[0].filled == (D(1), D(1))  # type: ignore[attr-defined]
    assert not [a for a in sim.log if isinstance(a, PlaceLeg)][2:]


def test_row11_sibling_fill_after_cancel_requested() -> None:
    sim = _armed_oco().fill(0, 1)
    assert sim.cancels == [1]
    sim.fill(1, "0.3")
    assert sim.rec.state is S.DEGRADED
    assert sim.rec.winner_leg_index == 0


def test_row11_canceled_with_fill_sibling() -> None:
    sim = _armed_oco().fill(0, 1)
    sim.cancel_out(1, CancelOutcome.CANCELED).fill(1, "0.2")
    assert sim.rec.degraded_reasons == {DegradedReason.DOUBLE_FILL}


def test_row11_deferred_unknown_leg_resolving_filled() -> None:
    sim = Sim(oco_spec()).place(0, "unknown").place(1).fill(1, 1)
    sim.snap(0, OS.FILLED, 1)
    assert sim.rec.state is S.DEGRADED
    assert sim.events(K.TRIGGERED)[0].deferred is True  # type: ignore[attr-defined]


def test_row24_late_winner_fill_after_completed_updates_only() -> None:
    sim = _armed_oco().fill(0, "0.4").cancel_out(1, CancelOutcome.CANCELED)
    sim.fill(0, "0.6")
    assert sim.rec.state is S.COMPLETED
    assert sim.kinds == [K.LEG_UPDATED]


def test_row24_stale_and_duplicate_reports_are_ignored() -> None:
    sim = _armed_oco().fill(0, "0.4")
    sim.update(0, OS.OPEN)  # stale OPEN after PARTIALLY_FILLED
    assert sim.last == ()
    assert sim.status(0) is LS.PARTIALLY_FILLED
    sim.fill(0, "0.4")  # duplicate cumulative
    assert sim.last == ()
    sim.fill(0, "0.3")  # lower cumulative
    assert sim.last == ()
    sim.update(0, OS.FILLED)
    sim.update(0, OS.OPEN)  # terminal never regresses
    assert sim.status(0) is LS.FILLED


def test_row25_tombstone_sibling_fill_reopens_as_degraded_and_is_saved() -> None:
    sim = _armed_oco().fill(0, 1).cancel_out(1, CancelOutcome.CANCELED)
    assert sim.deleted
    assert sim.rec.state is S.COMPLETED
    sim.fill(1, "0.5")
    assert sim.rec.state is S.DEGRADED
    assert Persist() in sim.last
    assert K.DEGRADED in sim.kinds
    assert not sim.cancels


def test_row25_tombstone_ignores_stale_events() -> None:
    sim = _armed_oco().fill(0, 1).cancel_out(1, CancelOutcome.CANCELED)
    sim.update(1, OS.OPEN)
    sim.fill(0, 1)
    assert sim.last == ()
    assert sim.rec.state is S.COMPLETED


# ---------------------------------------------------------------- rows 12-14, 16


def test_row12_terminal_entry_waits_for_get_leg_confirmation() -> None:
    sim = Sim(bracket_spec()).place(0)
    sim.fill(0, 2)
    assert sim.rec.state is S.ENTRY_WORKING
    assert sim.get_legs == [0]
    assert sim.leg(0).unresolved_since is not None


def test_row12_partial_entry_keeps_working_with_growing_fill() -> None:
    sim = Sim(bracket_spec()).place(0)
    sim.fill(0, "0.5")
    sim.fill(0, "1.0")
    assert sim.rec.state is S.ENTRY_WORKING
    assert sim.leg(0).filled == D("1.0")
    assert sim.kinds == [K.LEG_UPDATED]


def test_row12_filled_status_with_zero_fill_waits_even_after_snapshot() -> None:
    sim = Sim(bracket_spec()).place(0).update(0, OS.FILLED)
    assert sim.get_legs == [0]
    sim.snap(0, OS.FILLED, 0)
    assert sim.rec.state is S.ENTRY_WORKING
    sim.tick(31)
    assert DegradedReason.UNRESOLVED_PAST_GRACE in sim.rec.degraded_reasons
    sim.snap(0, OS.FILLED, 2)
    assert sim.leg(0).filled == D(2)


def test_row13_confirmed_fill_places_exits_sized_to_filled() -> None:
    sim = _bracket_exits_placing("2")
    assert sim.rec.state is S.EXITS_PLACING
    sim.begin(1)
    assert sim.leg(1).placed_amount == D(2)


def test_row13_partial_entry_exits_are_resized() -> None:
    sim = _bracket_exits_placing("0.5")
    assert sim.rec.state is S.EXITS_PLACING
    sim.place(1).place(2)
    assert sim.leg(1).placed_amount == D("0.5")
    assert sim.leg(2).placed_amount == D("0.5")
    assert sim.rec.state is S.ARMED


def test_row14_zero_fill_entry_canceled_or_failed() -> None:
    sim = Sim(bracket_spec()).place(0).update(0, OS.CANCELED)
    assert sim.rec.state is S.ENTRY_WORKING
    sim.snap(0, OS.CANCELED, 0)
    assert sim.rec.state is S.CANCELED
    assert [leg.status for leg in sim.rec.legs[1:]] == [LS.NOT_PLACED, LS.NOT_PLACED]
    failed = Sim(bracket_spec()).place(0).update(0, OS.FAILED).snap(0, OS.FAILED)
    assert failed.rec.state is S.FAILED
    assert failed.deleted


def test_row16_all_exits_submitted_is_armed_single_exit_fill_completes() -> None:
    sim = _bracket_exits_placing(sl=False)
    sim.place(1)
    assert sim.rec.state is S.ARMED
    sim.fill(1, 2)
    assert sim.rec.state is S.COMPLETED
    assert sim.kinds[:2] == [K.LEG_UPDATED, K.TRIGGERED]
    assert sim.deleted


def test_bracket_exit_fill_cancels_other_exit() -> None:
    sim = _bracket_exits_placing().place_exits()
    assert sim.rec.state is S.ARMED
    sim.fill(2, "1")
    assert sim.rec.state is S.TRIGGERED
    assert sim.cancels == [1]


def test_trigger_during_exits_placing_stops_remaining_exits() -> None:
    sim = _bracket_exits_placing().place(1)
    assert sim.rec.state is S.EXITS_PLACING
    sim.fill(1, 2)
    assert sim.status(2) is LS.NOT_PLACED
    assert not can_place(sim.rec)


# ---------------------------------------------------------------- rows 17-19


def test_row17_cancel_armed_group_cancels_every_live_leg() -> None:
    sim = _armed_oco().cancel()
    assert sim.rec.state is S.CANCELLING
    assert sorted(sim.cancels) == [0, 1]
    sim.cancel_out(0, CancelOutcome.CANCELED).cancel_out(1, CancelOutcome.CANCELED)
    assert sim.rec.state is S.CANCELED
    assert K.CANCELED in sim.kinds
    assert sim.deleted


def test_row17_cancel_is_idempotent_and_ignored_after_outcome() -> None:
    sim = _armed_oco().cancel()
    sim.cancel()
    assert sim.last == ()
    done = Sim(oco_spec()).place(0, "reject")
    done.cancel()
    assert done.last == ()


def test_row17_unknown_leg_is_cancelled_when_it_resolves() -> None:
    sim = Sim(oco_spec()).place(0, "unknown").place(1).cancel()
    assert sim.cancels == [1]
    sim.snap(0, OS.OPEN)
    assert sim.cancels == [0]


def test_row17_cancel_in_entry_working_never_places_exits() -> None:
    sim = Sim(bracket_spec()).place(0).cancel()
    assert sim.cancels == [0]
    assert [leg.status for leg in sim.rec.legs[1:]] == [LS.NOT_PLACED, LS.NOT_PLACED]
    sim.fill(0, "0.5")
    sim.cancel_out(0, CancelOutcome.CANCELED)
    assert sim.rec.state is S.CANCELLING
    assert sim.get_legs == [0]
    sim.snap(0, OS.CANCELED, "0.5")
    assert sim.rec.state is S.CANCELED
    assert residual_filled(sim.rec) == D("0.5")
    event = sim.events(K.CANCELED)[0]
    assert event.residual_filled == D("0.5")  # type: ignore[attr-defined]


def test_row17_cancel_during_degraded_still_cancels() -> None:
    sim = Sim(oco_spec()).place(0, "unknown").place(1).tick(31)
    assert sim.rec.state is S.DEGRADED
    sim.cancel()
    assert sim.rec.state is S.DEGRADED
    assert sim.cancels == [1]


def test_row18_cancelling_first_fill_sets_winner_second_is_double_fill() -> None:
    sim = _armed_oco().cancel()
    sim.fill(0, 1)
    assert sim.rec.state is S.CANCELLING
    assert sim.rec.winner_leg_index == 0
    sim.fill(1, 1)
    assert sim.rec.state is S.DEGRADED
    assert DegradedReason.DOUBLE_FILL in sim.rec.degraded_reasons


def test_row19_cancel_with_winner_reports_residual() -> None:
    sim = _armed_oco().cancel().fill(0, "0.4")
    sim.cancel_out(0, CancelOutcome.CANCELED).cancel_out(1, CancelOutcome.CANCELED)
    assert sim.rec.state is S.CANCELED
    assert sim.events(K.CANCELED)[0].residual_filled == D("0.4")  # type: ignore[attr-defined]


# ---------------------------------------------------------------- rows 20-23


def test_row20_past_grace_degrades_once() -> None:
    sim = Sim(oco_spec()).place(0, "unknown").place(1)
    sim.tick(10)
    assert sim.rec.state is S.ARMED
    assert sim.get_legs == [0]
    sim.tick(30)
    assert sim.rec.state is S.DEGRADED
    assert DegradedReason.UNRESOLVED_PAST_GRACE in sim.rec.degraded_reasons
    sim.tick(60)
    assert len(sim.events(K.DEGRADED)) == 1


def test_row21_uncertain_cancel_outcome_polls_then_resends_cancel() -> None:
    sim = _armed_oco().cancel()
    sim.cancel_out(0, CancelOutcome.NOT_FOUND)
    sim.cancel_out(1, CancelOutcome.UNKNOWN)
    assert sim.rec.state is S.CANCELLING
    sim.tick(1)
    assert sorted(sim.get_legs) == [0, 1]
    sim.snap(0, None)
    assert sim.status(0) is LS.UNKNOWN
    sim.snap(0, OS.OPEN)
    assert sim.cancels == [0]
    sim.snap(1, OS.CANCELED)
    sim.cancel_out(0, CancelOutcome.CANCELED)
    assert sim.rec.state is S.CANCELED


def test_row21_not_found_stays_unresolved_until_get_leg_answers() -> None:
    sim = _armed_oco().cancel().cancel_out(0, CancelOutcome.NOT_FOUND)
    sim.update(0, OS.OPEN)
    sim.cancel_out(1, CancelOutcome.CANCELED)
    assert sim.rec.state is S.CANCELLING
    sim.snap(0, OS.CANCELED)
    assert sim.rec.state is S.CANCELED


def test_row22_external_cancel_keeps_or_breaks_link() -> None:
    sim = _armed_oco(3)
    sim.update(0, OS.CANCELED)
    assert sim.rec.state is S.ARMED
    assert sim.kinds == [K.LEG_UPDATED]
    sim.update(1, OS.CANCELED)
    assert sim.rec.state is S.DEGRADED
    assert sim.rec.degraded_reasons == {DegradedReason.LINK_BROKEN}
    two = _armed_oco().update(1, OS.FAILED)
    assert two.rec.degraded_reasons == {DegradedReason.LINK_BROKEN}


def test_row23_degraded_keeps_cancelling_and_never_places() -> None:
    sim = Sim(oco_spec()).place(0, "unknown").place(1).fill(1, 1)
    sim.tick(31)
    assert sim.rec.state is S.DEGRADED
    assert sim.cancels == []
    sim.snap(0, OS.OPEN)
    assert sim.cancels == [0]
    assert not can_place(sim.rec)
    sim.cancel_out(0, CancelOutcome.CANCELED)
    assert sim.deleted
    assert sim.rec.state is S.DEGRADED


# ---------------------------------------------------------------- misc


def test_unknown_client_order_ids_change_nothing() -> None:
    sim = _armed_oco()
    assert apply_update(sim.rec, "nope", OS.OPEN, 0.0).actions == ()
    assert apply_fill(sim.rec, LegFill("nope", D(1), D(1), 0.0), 0.0).actions == ()


def test_cancel_actions_only_reference_known_legs() -> None:
    sim = _armed_oco().fill(0, 1)
    assert all(a.leg_index in (0, 1) for a in sim.log if isinstance(a, CancelLeg))
