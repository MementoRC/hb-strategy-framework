"""Seeded random walks over the pure state machine; I1-I8 are asserted on every step."""

from __future__ import annotations

import random
from decimal import Decimal

import pytest
from data_type_primitives import LinkKind, OrderState

from strategy_framework.linked_orders.state import awaiting_reply, can_place
from strategy_framework.linked_orders.types import CancelOutcome, GroupState
from tests.unit.linked_orders.builders import Sim, bracket_spec, oco_spec

D = Decimal
_SPECS = [
    lambda: oco_spec(2),
    lambda: oco_spec(3),
    bracket_spec,
    lambda: bracket_spec(stop_loss=False),
]
_STATES = list(OrderState)
_SNAP_STATES = [
    OrderState.OPEN,
    OrderState.PARTIALLY_FILLED,
    OrderState.FILLED,
    OrderState.CANCELED,
    OrderState.FAILED,
    OrderState.UNKNOWN,
]
_OUTCOMES = list(CancelOutcome)


def _ids(sim: Sim) -> list[int]:
    return [leg.leg_index for leg in sim.rec.legs if leg.client_order_id is not None]


def _op_begin(sim: Sim, rng: random.Random) -> None:
    rec = sim.rec
    i = len(rec.legs)
    if not can_place(rec) or i >= len(rec.spec.legs) or any(map(awaiting_reply, rec.legs)):
        return
    if rec.spec.kind is LinkKind.BRACKET and (rec.state is GroupState.PLACING) != (i == 0):
        return
    sim.begin(i)


def _op_reply(sim: Sim, rng: random.Random) -> None:
    pending = [leg.leg_index for leg in sim.rec.legs if awaiting_reply(leg)]
    if pending:
        sim.reply(pending[0], rng.choice(["ok", "ok", "ok", "unknown", "reject"]))


def _op_update(sim: Sim, rng: random.Random) -> None:
    ids = _ids(sim)
    if ids:
        sim.update(rng.choice(ids), rng.choice(_STATES))


def _op_fill(sim: Sim, rng: random.Random) -> None:
    ids = _ids(sim)
    if ids:
        i = rng.choice(ids)
        placed = sim.leg(i).placed_amount
        sim.fill(i, str(placed * D(rng.randint(1, 4)) / 4))


def _op_snap(sim: Sim, rng: random.Random) -> None:
    ids = _ids(sim)
    if not ids:
        return
    i = rng.choice(ids)
    placed = sim.leg(i).placed_amount
    state = rng.choice([*_SNAP_STATES, None])
    sim.snap(i, state, str(placed * D(rng.randint(0, 2)) / 2))


def _op_cancel_out(sim: Sim, rng: random.Random) -> None:
    ids = _ids(sim)
    if ids:
        sim.cancel_out(rng.choice(ids), rng.choice(_OUTCOMES))


def _op_cancel(sim: Sim, rng: random.Random) -> None:
    sim.cancel()


def _op_tick(sim: Sim, rng: random.Random) -> None:
    sim.tick(rng.choice([0.0, 5.0, 40.0]))


_OPS = [
    _op_begin,
    _op_begin,
    _op_reply,
    _op_reply,
    _op_update,
    _op_fill,
    _op_snap,
    _op_cancel_out,
    _op_tick,
    _op_cancel,
]


@pytest.mark.parametrize("seed", range(400))
def test_random_walk_keeps_invariants(seed: int) -> None:
    rng = random.Random(seed)
    sim = Sim(rng.choice(_SPECS)())
    for _ in range(70):
        rng.choice(_OPS)(sim, rng)
