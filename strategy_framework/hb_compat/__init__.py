"""hb_compat — adapters for integrating strategy-framework into host environments.

Contains protocol-based composition layers with no host-framework imports,
allowing host bridges (e.g. hummingbot's OrchestratorBridge) to import and
delegate without creating circular dependencies.
"""

from strategy_framework.hb_compat.event_bus_adapter import EventBusAdapter
from strategy_framework.hb_compat.logger_adapter import get_logger
from strategy_framework.hb_compat.orchestrator_adapter import OrchestratorAdapter

__all__ = ["EventBusAdapter", "OrchestratorAdapter", "get_logger"]
