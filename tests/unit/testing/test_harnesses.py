"""Tests for test harnesses."""

from decimal import Decimal

from strategy_framework.testing.harnesses import ExecutorTestHarness
from strategy_framework.testing.mock_market import MockMarketAccess


class TestExecutorTestHarness:
    def test_creation(self):
        harness = ExecutorTestHarness()
        assert isinstance(harness.market, MockMarketAccess)

    def test_custom_mid_price(self):
        harness = ExecutorTestHarness(mid_price=Decimal("42000"))
        assert harness.market.get_mid_price() == Decimal("42000")

    def test_simulate_price_move(self):
        harness = ExecutorTestHarness(mid_price=Decimal("50000"))
        harness.set_price(Decimal("51000"))
        assert harness.market.get_mid_price() == Decimal("51000")

    def test_place_and_track_order(self):
        harness = ExecutorTestHarness()
        order_id = harness.market.place_order("limit", "buy", Decimal("1"), Decimal("50000"))
        assert len(harness.market.order_history) == 1
        assert order_id.startswith("mock_")
