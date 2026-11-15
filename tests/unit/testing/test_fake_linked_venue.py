"""Fake linked venue, codecs, manual clock and recording emitter."""

from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest
from data_type_primitives import (
    LegRole,
    LegSpec,
    OrderOutcomeUnknownError,
    OrderState,
    OrderType,
    TradeType,
)

from strategy_framework.linked_orders.protocols import (
    ClockProtocol,
    EmulationVenue,
    LinkedEventEmitter,
    LinkedOrderIdCodec,
)
from strategy_framework.linked_orders.types import CancelOutcome
from strategy_framework.testing.fake_linked_venue import (
    FakeEmulationVenue,
    Int32LinkIdCodec,
    ManualClock,
    RecordingEmitter,
    StringLinkIdCodec,
    VenueRejectedError,
)

D = Decimal
TARGET = "BTC-USD"


def _leg(order_type: OrderType = OrderType.LIMIT, amount: str = "2") -> LegSpec:
    return LegSpec(
        role=LegRole.OCO_LEG,
        order_type=order_type,
        trade_type=TradeType.SELL,
        amount=D(amount),
        price=D(100) if order_type.is_limit_type() else None,
    )


@pytest.fixture
def venue() -> FakeEmulationVenue:
    return FakeEmulationVenue()


def test_fakes_satisfy_protocols(venue: FakeEmulationVenue) -> None:
    assert isinstance(venue, EmulationVenue)
    assert isinstance(StringLinkIdCodec(), LinkedOrderIdCodec)
    assert isinstance(Int32LinkIdCodec(), LinkedOrderIdCodec)
    assert isinstance(ManualClock(), ClockProtocol)
    assert isinstance(RecordingEmitter(), LinkedEventEmitter)


@pytest.mark.parametrize("codec", [StringLinkIdCodec(), Int32LinkIdCodec()])
def test_codecs_round_trip(codec: LinkedOrderIdCodec) -> None:
    for group_id in (0, 1, 12345):
        for leg in (0, 1, 15):
            assert codec.decode(codec.encode(group_id, leg)) == (group_id, leg)


def test_string_codec_ignores_foreign_tags() -> None:
    codec = StringLinkIdCodec()
    assert codec.decode("other-1-2") is None
    assert codec.decode("hbl-1") is None
    assert codec.decode("hbl-a-b") is None
    assert codec.decode(5) is None


def test_int32_codec_refuses_overflow_and_ignores_foreign_tags() -> None:
    codec = Int32LinkIdCodec()
    with pytest.raises(ValueError, match="overflows"):
        codec.encode(2**27, 0)
    with pytest.raises(ValueError, match="cannot encode"):
        codec.encode(1, 16)
    with pytest.raises(ValueError, match="cannot encode"):
        codec.encode(-1, 0)
    assert codec.decode("x") is None
    assert codec.decode(-5) is None
    assert codec.decode(2**31) is None
    assert codec.decode(True) is None


def test_manual_clock_and_emitter() -> None:
    clock = ManualClock(10.0)
    assert clock.time() == 10.0
    assert clock.advance(5) == 15.0
    emitter = RecordingEmitter()
    emitter.emit("linked.group", object())
    emitter.emit("other", "payload")
    assert [t for t, _ in emitter.events] == ["linked.group", "other"]
    assert emitter.payloads()[1] == "payload"
    assert emitter.kinds() == [None, None]


async def test_place_records_tag_and_supports_native_types() -> None:
    venue = FakeEmulationVenue(native_types=[OrderType.LIMIT])
    assert venue.supports_leg(TARGET, _leg())
    assert not venue.supports_leg(TARGET, _leg(OrderType.MARKET))
    cid = await venue.place_leg(TARGET, _leg(), link_tag="hbl-1-0")
    assert venue.snapshot(cid).link_tag == "hbl-1-0"
    assert venue.calls("place_leg")[0][3] == "hbl-1-0"


async def test_scripted_placement_modes(venue: FakeEmulationVenue) -> None:
    venue.script_place("unknown", "reject")
    with pytest.raises(OrderOutcomeUnknownError) as info:
        await venue.place_leg(TARGET, _leg(), link_tag=1)
    assert info.value.client_order_id in venue.orders
    with pytest.raises(VenueRejectedError):
        await venue.place_leg(TARGET, _leg(), link_tag=2)
    assert len(venue.orders) == 1
    assert len(venue.calls("place_leg")) == 2


async def test_reply_delay_is_controllable(venue: FakeEmulationVenue) -> None:
    venue.hold("place_leg")
    task = asyncio.ensure_future(venue.place_leg(TARGET, _leg(), link_tag="a"))
    await asyncio.sleep(0)
    assert not task.done()
    assert venue.waiting("place_leg") == 1
    assert venue.orders  # the effect happened; only the reply is delayed
    assert venue.release("place_leg") == 1
    assert (await task) in venue.orders
    assert venue.release("place_leg") == 0


async def test_release_all_unholds(venue: FakeEmulationVenue) -> None:
    venue.hold("cancel_leg")
    cid = await venue.place_leg(TARGET, _leg(), link_tag="a")
    first = asyncio.ensure_future(venue.cancel_leg(TARGET, cid))
    second = asyncio.ensure_future(venue.cancel_leg(TARGET, cid))
    await asyncio.sleep(0)
    assert venue.release_all("cancel_leg") == 2
    assert [await first, await second] == [CancelOutcome.CANCELED, CancelOutcome.CANCELED]
    assert await venue.cancel_leg(TARGET, cid) == CancelOutcome.CANCELED


async def test_fill_update_and_default_cancel_outcomes(venue: FakeEmulationVenue) -> None:
    cid = await venue.place_leg(TARGET, _leg(), link_tag="a")
    partial = venue.fill(cid, "0.5", fill_id="t1")
    assert (partial.cumulative_filled, partial.fill_id) == (D("0.5"), "t1")
    assert venue.snapshot(cid).state is OrderState.PARTIALLY_FILLED
    assert venue.fill(cid, 2).cumulative_filled == D(2)
    assert venue.snapshot(cid).state is OrderState.FILLED
    assert await venue.cancel_leg(TARGET, cid) == CancelOutcome.ALREADY_FILLED
    assert await venue.cancel_leg(TARGET, "missing") == CancelOutcome.NOT_FOUND
    other = await venue.place_leg(TARGET, _leg(), link_tag="b")
    update = venue.update(other, OrderState.CANCELED)
    assert (update.client_order_id, update.new_state) == (other, OrderState.CANCELED)


async def test_scripted_cancel_outcomes_apply_effects(venue: FakeEmulationVenue) -> None:
    a = await venue.place_leg(TARGET, _leg(), link_tag="a")
    b = await venue.place_leg(TARGET, _leg(), link_tag="b")
    c = await venue.place_leg(TARGET, _leg(), link_tag="c")
    venue.script_cancel(CancelOutcome.ALREADY_FILLED, CancelOutcome.UNKNOWN, CancelOutcome.CANCELED)
    assert await venue.cancel_leg(TARGET, a) == CancelOutcome.ALREADY_FILLED
    assert venue.snapshot(a).state is OrderState.FILLED
    assert venue.snapshot(a).filled == D(2)
    assert await venue.cancel_leg(TARGET, b) == CancelOutcome.UNKNOWN
    assert venue.snapshot(b).state is OrderState.OPEN
    assert await venue.cancel_leg(TARGET, c) == CancelOutcome.CANCELED
    assert venue.snapshot(c).state is OrderState.CANCELED


async def test_get_leg_by_either_key_and_script(venue: FakeEmulationVenue) -> None:
    cid = await venue.place_leg(TARGET, _leg(), link_tag="tag-1")
    by_id = await venue.get_leg(TARGET, client_order_id=cid)
    by_tag = await venue.get_leg(TARGET, link_tag="tag-1")
    assert by_id == by_tag == venue.snapshot(cid)
    assert await venue.get_leg(TARGET, client_order_id="nope") is None
    venue.script_get(None, venue.snapshot(cid))
    assert await venue.get_leg(TARGET, client_order_id=cid) is None
    assert await venue.get_leg(TARGET, client_order_id=cid) == venue.snapshot(cid)
    with pytest.raises(ValueError, match="exactly one"):
        await venue.get_leg(TARGET)
    with pytest.raises(ValueError, match="exactly one"):
        await venue.get_leg(TARGET, client_order_id=cid, link_tag="tag-1")


async def test_list_open_legs_excludes_terminal_and_other_targets(
    venue: FakeEmulationVenue,
) -> None:
    open_cid = await venue.place_leg(TARGET, _leg(), link_tag="a")
    done = await venue.place_leg(TARGET, _leg(), link_tag="b")
    await venue.place_leg("ETH-USD", _leg(), link_tag="c")
    venue.update(done, OrderState.CANCELED)
    assert [s.client_order_id for s in await venue.list_open_legs(TARGET)] == [open_cid]
    assert venue.calls("list_open_legs") == [("list_open_legs", TARGET)]
