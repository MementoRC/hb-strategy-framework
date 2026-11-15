"""Monotonic leg rule and intake helpers (cumulative fills, fill_id)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from strategy_framework.linked_orders.state import FillIntake, merge_filled, merge_status
from strategy_framework.linked_orders.types import TERMINAL_STATUSES, LegFill, LegStatus

D = Decimal
LS = LegStatus


@pytest.mark.parametrize("terminal", sorted(TERMINAL_STATUSES, key=lambda s: s.name))
@pytest.mark.parametrize("new", list(LegStatus))
def test_terminal_status_never_changes(terminal: LegStatus, new: LegStatus) -> None:
    assert merge_status(terminal, new) is terminal


@pytest.mark.parametrize("old", [LS.PENDING_CREATE, LS.UNKNOWN])
@pytest.mark.parametrize("new", list(LegStatus))
def test_unresolved_may_move_anywhere(old: LegStatus, new: LegStatus) -> None:
    assert merge_status(old, new) is new


@pytest.mark.parametrize("stale", [LS.OPEN, LS.CREATED, LS.APPROVED, LS.PENDING_APPROVAL])
def test_partial_never_goes_back_to_open(stale: LegStatus) -> None:
    assert merge_status(LS.PARTIALLY_FILLED, stale) is LS.PARTIALLY_FILLED


def test_live_statuses_may_progress_or_become_unknown() -> None:
    assert merge_status(LS.OPEN, LS.PARTIALLY_FILLED) is LS.PARTIALLY_FILLED
    assert merge_status(LS.OPEN, LS.UNKNOWN) is LS.UNKNOWN
    assert merge_status(LS.PARTIALLY_FILLED, LS.UNKNOWN) is LS.UNKNOWN
    assert merge_status(LS.PARTIALLY_FILLED, LS.PENDING_CANCEL) is LS.PENDING_CANCEL
    assert merge_status(LS.OPEN, LS.PENDING_CREATE) is LS.OPEN


def test_filled_is_max() -> None:
    assert merge_filled(D(2), D(1)) == D(2)
    assert merge_filled(D(1), D(2)) == D(2)


def _fill(cumulative: str, fill_id: str | None = None) -> LegFill:
    return LegFill("c0", D(cumulative), D(100), 0.0, fill_id)


def test_intake_accepts_only_growth() -> None:
    intake = FillIntake()
    assert intake.accept(_fill("1"), D(0))
    assert not intake.accept(_fill("1"), D(1))
    assert not intake.accept(_fill("0.5"), D(1))


def test_intake_drops_seen_fill_id() -> None:
    intake = FillIntake()
    assert intake.accept(_fill("1", "t1"), D(0))
    assert not intake.accept(_fill("2", "t1"), D(1))
    assert intake.accept(_fill("2", "t2"), D(1))


def test_intake_does_not_remember_ids_of_dropped_fills() -> None:
    intake = FillIntake()
    assert not intake.accept(_fill("1", "t1"), D(1))
    assert intake.accept(_fill("2", "t1"), D(1))


def test_intake_seen_set_is_bounded() -> None:
    intake = FillIntake(max_seen=2)
    for n, fid in enumerate(["a", "b", "c"], start=1):
        assert intake.accept(_fill(str(n), fid), D(n - 1))
    assert intake.accept(_fill("9", "a"), D(8))  # "a" was evicted
    assert not intake.accept(_fill("10", "c"), D(9))
