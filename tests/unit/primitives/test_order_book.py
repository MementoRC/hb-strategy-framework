"""Tests for OrderBookSnapshot frozen model."""
from decimal import Decimal

import pytest

from strategy_framework.primitives.order_book import OrderBookEntry, OrderBookSnapshot


class TestOrderBookEntry:
    """OrderBookEntry is a price/quantity pair."""

    def test_create(self) -> None:
        entry = OrderBookEntry(price=Decimal("100.5"), quantity=Decimal("10.0"))
        assert entry.price == Decimal("100.5")
        assert entry.quantity == Decimal("10.0")

    def test_frozen(self) -> None:
        entry = OrderBookEntry(price=Decimal("100"), quantity=Decimal("10"))
        with pytest.raises(Exception):
            entry.price = Decimal("999")  # type: ignore[misc]

    def test_coerces_strings(self) -> None:
        entry = OrderBookEntry(price="100.5", quantity="10.0")
        assert isinstance(entry.price, Decimal)


class TestOrderBookSnapshot:
    """OrderBookSnapshot captures bids/asks at a point in time."""

    def test_create(self) -> None:
        snap = OrderBookSnapshot(
            timestamp=1700000000000,
            bids=[OrderBookEntry(price=Decimal("99"), quantity=Decimal("10"))],
            asks=[OrderBookEntry(price=Decimal("101"), quantity=Decimal("5"))],
        )
        assert snap.timestamp == 1700000000000
        assert len(snap.bids) == 1
        assert len(snap.asks) == 1
        assert snap.bids[0].price == Decimal("99")
        assert snap.asks[0].price == Decimal("101")

    def test_frozen(self) -> None:
        snap = OrderBookSnapshot(timestamp=0, bids=[], asks=[])
        with pytest.raises(Exception):
            snap.timestamp = 999  # type: ignore[misc]

    def test_empty_book(self) -> None:
        snap = OrderBookSnapshot(timestamp=0, bids=[], asks=[])
        assert snap.bids == []
        assert snap.asks == []

    def test_best_bid_ask(self) -> None:
        snap = OrderBookSnapshot(
            timestamp=0,
            bids=[
                OrderBookEntry(price=Decimal("99"), quantity=Decimal("10")),
                OrderBookEntry(price=Decimal("98"), quantity=Decimal("20")),
            ],
            asks=[
                OrderBookEntry(price=Decimal("101"), quantity=Decimal("5")),
                OrderBookEntry(price=Decimal("102"), quantity=Decimal("15")),
            ],
        )
        assert snap.best_bid == Decimal("99")
        assert snap.best_ask == Decimal("101")
        assert snap.spread == Decimal("2")

    def test_best_bid_ask_empty_raises(self) -> None:
        snap = OrderBookSnapshot(timestamp=0, bids=[], asks=[])
        with pytest.raises(ValueError, match="empty"):
            _ = snap.best_bid
        with pytest.raises(ValueError, match="empty"):
            _ = snap.best_ask
