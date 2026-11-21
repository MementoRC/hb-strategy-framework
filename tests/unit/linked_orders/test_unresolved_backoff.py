"""Exponential backoff of `get_leg` retries for unresolved legs (issue #95)."""

from __future__ import annotations

import math

import pytest
from data_type_primitives import OrderState

from strategy_framework.linked_orders import LinkedOrderManagerConfig
from strategy_framework.linked_orders.config import RetryBackoff
from strategy_framework.linked_orders.state import Persist
from strategy_framework.linked_orders.types import CancelOutcome, DegradedReason, GroupState
from tests.unit.linked_orders.builders import Sim, oco_spec


def _unknown_leg() -> Sim:
    """Leg 0 UNKNOWN (unresolved since sim.now), leg 1 live."""
    return Sim(oco_spec()).place(0, "unknown").place(1)


def _attempt_times(sim: Sim, retry: RetryBackoff, horizon: float) -> list[float]:
    start, times = sim.now, []
    while sim.now - start < horizon:
        sim.tick(0.5, grace=1e9, retry=retry)
        if sim.get_legs:
            times.append(sim.now - start)
    return times


def test_no_get_leg_before_base_elapses() -> None:
    sim = _unknown_leg()
    sim.tick(0.0)
    assert sim.get_legs == []
    sim.tick(0.5)
    assert sim.get_legs == []
    sim.tick(0.5)
    assert sim.get_legs == [0]


def test_spacing_grows_by_multiplier() -> None:
    times = _attempt_times(_unknown_leg(), RetryBackoff(1.0, 2.0, 60.0), 40.0)
    assert times == [1.0, 3.0, 7.0, 15.0, 31.0]


def test_spacing_is_capped_at_max() -> None:
    times = _attempt_times(_unknown_leg(), RetryBackoff(1.0, 2.0, 5.0), 20.0)
    assert times == [1.0, 3.0, 7.0, 12.0, 17.0]


def test_multiplier_one_keeps_constant_spacing() -> None:
    times = _attempt_times(_unknown_leg(), RetryBackoff(2.0, 1.0, 2.0), 9.0)
    assert times == [2.0, 4.0, 6.0, 8.0]


def test_backoff_state_resets_after_resolution() -> None:
    sim = _armed_with_uncertain_cancel()
    sim.tick(1)
    assert sim.get_legs == [0]
    sim.tick(2)
    assert sim.get_legs == [0]
    assert sim.leg(0).retry_delay_s == 4.0
    sim.snap(0, OrderState.OPEN)  # resolves: cancel is re-sent
    assert sim.leg(0).unresolved_since is None
    assert (sim.leg(0).retry_at, sim.leg(0).retry_delay_s) == (None, None)
    sim.cancel_out(0, CancelOutcome.NOT_FOUND)  # unresolved again: fresh schedule
    sim.tick(0.5)
    assert sim.get_legs == []
    sim.tick(0.5)
    assert sim.get_legs == [0]
    assert sim.leg(0).retry_delay_s == 2.0


def _armed_with_uncertain_cancel() -> Sim:
    sim = Sim(oco_spec()).place_all().cancel()
    sim.cancel_out(1, CancelOutcome.CANCELED)
    sim.cancel_out(0, CancelOutcome.NOT_FOUND)
    return sim


def test_retry_bookkeeping_alone_does_not_persist() -> None:
    sim = _unknown_leg()
    sim.tick(1.0)
    assert sim.get_legs == [0]
    assert not any(isinstance(a, Persist) for a in sim.last)


@pytest.mark.parametrize("backoff", [RetryBackoff(), RetryBackoff(100.0, 2.0, 100.0)])
def test_grace_degradation_unchanged_by_backoff(backoff: RetryBackoff) -> None:
    sim = _unknown_leg()
    sim.tick(30.0, retry=backoff)
    assert sim.rec.state is GroupState.ARMED
    sim.tick(1.0, retry=backoff)
    assert sim.rec.state is GroupState.DEGRADED
    assert DegradedReason.UNRESOLVED_PAST_GRACE in sim.rec.degraded_reasons


def test_config_defaults_and_retry_view() -> None:
    cfg = LinkedOrderManagerConfig()
    assert (cfg.unresolved_retry_base_s, cfg.unresolved_retry_multiplier) == (1.0, 2.0)
    assert cfg.unresolved_retry_max_s == 60.0
    assert cfg.retry == RetryBackoff(1.0, 2.0, 60.0)


@pytest.mark.parametrize("value", [0, -1])
def test_base_must_be_positive(value: float) -> None:
    with pytest.raises(ValueError, match="unresolved_retry_base_s"):
        LinkedOrderManagerConfig(unresolved_retry_base_s=value)


@pytest.mark.parametrize("name", ["base", "multiplier", "max"])
@pytest.mark.parametrize("value", [math.nan, math.inf])
def test_retry_settings_must_be_finite(name: str, value: float) -> None:
    field = f"unresolved_retry_{name}" + ("" if name == "multiplier" else "_s")
    with pytest.raises(ValueError, match=field):
        LinkedOrderManagerConfig(**{field: value})


def test_multiplier_must_be_at_least_one() -> None:
    assert LinkedOrderManagerConfig(unresolved_retry_multiplier=1).unresolved_retry_multiplier == 1
    with pytest.raises(ValueError, match="unresolved_retry_multiplier"):
        LinkedOrderManagerConfig(unresolved_retry_multiplier=0.9)


def test_max_must_not_be_below_base() -> None:
    assert LinkedOrderManagerConfig(unresolved_retry_base_s=5.0, unresolved_retry_max_s=5.0)
    with pytest.raises(ValueError, match="unresolved_retry_max_s"):
        LinkedOrderManagerConfig(unresolved_retry_base_s=5.0, unresolved_retry_max_s=4.0)
