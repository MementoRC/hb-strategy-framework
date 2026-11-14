"""Re-export shim; implementation lives in data_type_primitives.trading_rules.

See hb-strategy-framework#73.
"""

from __future__ import annotations

from data_type_primitives.trading_rules import TradingRules

__all__ = ["TradingRules"]
