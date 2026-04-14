"""OrchestratorAdapter — composition wrapper for poll-driven host environments.

Host frameworks (e.g. hummingbot) hold an OrchestratorAdapter and call
evaluate() each tick.  No host-framework types are imported here.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from strategy_framework.orchestrator import StrategyOrchestrator

if TYPE_CHECKING:
    from strategy_framework.protocols.event_bus import EventBusProtocol
    from strategy_framework.protocols.market import MarketAccessProtocol
    from strategy_framework.protocols.market_data import MarketDataProtocol
    from strategy_framework.primitives.enums import RunnableStatus


class OrchestratorAdapter:
    """Composition adapter that exposes StrategyOrchestrator to a host framework.

    The host framework (bridge) owns the lifecycle and calls evaluate() each
    tick.  All methods delegate directly to the underlying orchestrator.

    Usage::

        access = LiveMarketAccess(connector, "BTC-USDT")
        data   = LiveMarketData(market_data_provider, "binance")
        adapter = OrchestratorAdapter(access, data)
        adapter.register_controller(my_controller)
        # host bridge calls adapter.evaluate() each tick
    """

    def __init__(
        self,
        market_access: MarketAccessProtocol,
        market_data: MarketDataProtocol,
        event_bus: EventBusProtocol | None = None,
    ) -> None:
        self._orchestrator = StrategyOrchestrator(market_access, market_data, event_bus)

    # ── Tick entry point ──────────────────────────────────────────────────────

    def evaluate(self) -> None:
        """Drive the orchestrator one evaluation cycle."""
        self._orchestrator.evaluate()

    # ── Controller management ─────────────────────────────────────────────────

    def register_controller(self, controller: Any) -> None:
        self._orchestrator.register_controller(controller)

    def unregister_controller(self, controller_id: str) -> None:
        self._orchestrator.unregister_controller(controller_id)

    # ── OrchestratorProtocol delegation ──────────────────────────────────────

    def submit_actions(self, actions: list[Any]) -> None:
        self._orchestrator.submit_actions(actions)

    def get_executor_state(self, executor_id: str) -> RunnableStatus:
        return self._orchestrator.get_executor_state(executor_id)

    def get_active_executors(self, controller_id: str) -> list[str]:
        return self._orchestrator.get_active_executors(controller_id)

    # ── Introspection ─────────────────────────────────────────────────────────

    @property
    def orchestrator(self) -> StrategyOrchestrator:
        """The underlying StrategyOrchestrator instance."""
        return self._orchestrator
