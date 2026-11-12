"""Re-export of OrderType/TradeType for the ``hb_compat`` import path.

``TradeType``/``OrderType`` are defined once in
``strategy_framework.primitives.enums`` (which maps them to
``data_type_primitives.common`` via ``to_canonical``/``from_canonical``). This
module re-exports the same class objects so existing
``strategy_framework.hb_compat`` import paths keep resolving, plus the
``Canonical*`` aliases.
"""

from data_type_primitives.common import OrderType as CanonicalOrderType
from data_type_primitives.common import TradeType as CanonicalTradeType

from strategy_framework.primitives.enums import OrderType, TradeType

__all__ = ["CanonicalOrderType", "CanonicalTradeType", "OrderType", "TradeType"]
