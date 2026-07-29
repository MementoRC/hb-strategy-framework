"""Compatibility shim mapping this package's OrderType/TradeType onto the
canonical enums declared in ``hb-data-type-primitives`` (ADR 0001 L0 leaf).

Why this doesn't live in ``strategy_framework.primitives.enums``
------------------------------------------------------------------
``strategy_framework.primitives`` is itself classified as an L0 leaf in the
parent hummingbot repo's import-linter ``layers``/``adr-0001-l0-leaf-independence``
contracts (see ADR 0001, ``.importlinter``). L0 leaves must not import each
other, so ``primitives`` cannot depend on ``data_type_primitives`` (another L0
leaf) without creating a forbidden L0-to-L0 edge. ``primitives/enums.py``
therefore keeps its own local ``OrderType``/``TradeType`` redeclarations
unchanged.

This module lives outside ``primitives`` (in the L2-classified part of the
package, alongside the existing ``event_bus``/``orchestrator`` hb_compat
adapters), where a downward dependency on ``data_type_primitives`` is
permitted. It re-declares the same string-serialized enum surface previously
duplicated in ``primitives.enums`` — preserving pydantic (StrEnum) validation
and JSON-serialization compatibility for existing configs/tests — while
providing ``to_canonical``/``from_canonical`` conversions to interoperate with
the canonical ``data_type_primitives.common`` types. Internal consumers
outside ``primitives`` (executors, protocols, mixins) import from here.
"""

from enum import StrEnum

from data_type_primitives.common import OrderType as CanonicalOrderType
from data_type_primitives.common import TradeType as CanonicalTradeType

__all__ = ["CanonicalOrderType", "CanonicalTradeType", "OrderType", "TradeType"]


class TradeType(StrEnum):
    """Buy or sell.

    String-serialized (matches the historical ``primitives.enums.TradeType``
    values) for pydantic/config compatibility, with conversions to/from the
    canonical ``data_type_primitives.common.TradeType``.
    """

    BUY = "buy"
    SELL = "sell"

    @property
    def opposite(self) -> "TradeType":
        return TradeType.SELL if self == TradeType.BUY else TradeType.BUY

    def to_canonical(self) -> CanonicalTradeType:
        """Map to the canonical ``data_type_primitives`` enum member."""
        return CanonicalTradeType[self.name]

    @classmethod
    def from_canonical(cls, value: CanonicalTradeType) -> "TradeType":
        """Build from a canonical ``data_type_primitives`` enum member."""
        return cls[value.name]


class OrderType(StrEnum):
    """Order type for placement.

    String-serialized (matches the historical ``primitives.enums.OrderType``
    values) for pydantic/config compatibility, with conversions to/from the
    canonical ``data_type_primitives.common.OrderType``.
    """

    LIMIT = "limit"
    MARKET = "market"
    LIMIT_MAKER = "limit_maker"

    def to_canonical(self) -> CanonicalOrderType:
        """Map to the canonical ``data_type_primitives`` enum member."""
        return CanonicalOrderType[self.name]

    @classmethod
    def from_canonical(cls, value: CanonicalOrderType) -> "OrderType":
        """Build from a canonical ``data_type_primitives`` enum member.

        Only ``MARKET``, ``LIMIT``, and ``LIMIT_MAKER`` are representable;
        other canonical members (AMM/conditional order types) have no
        equivalent here and raise ``KeyError``.
        """
        return cls[value.name]
