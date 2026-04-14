"""hb_compat — adapters for integrating strategy-framework into host environments.

Contains protocol-based composition layers with no host-framework imports,
allowing host bridges (e.g. hummingbot's OrchestratorBridge) to import and
delegate without creating circular dependencies.
"""

from strategy_framework.hb_compat.orchestrator_adapter import OrchestratorAdapter

__all__ = ["OrchestratorAdapter"]
