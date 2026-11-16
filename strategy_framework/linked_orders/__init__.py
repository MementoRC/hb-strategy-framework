"""Opt-in emulated linked orders (OCO / BRACKET) for venues without native support.

Not re-exported from `strategy_framework`: import from here explicitly. Emulated OCO cannot
give native OCA guarantees; a sibling can fill before its cancel lands (double fill).
"""

from strategy_framework.linked_orders.config import LinkedOrderManagerConfig
from strategy_framework.linked_orders.errors import (
    EmulationNotEnabledError,
    GroupIdPersistenceError,
    GroupIdSpaceExhaustedError,
    GroupInvariantError,
    LinkedGroupNotFoundError,
    LinkedOrderError,
    LinkIdCodecError,
    RecoveryRequiredError,
    UnsupportedLegError,
    VolatileStoreError,
)
from strategy_framework.linked_orders.events import (
    LINKED_GROUP_EVENT,
    LinkedEventKind,
    LinkedGroupEvent,
)
from strategy_framework.linked_orders.manager import EmulatedLinkedOrderManager
from strategy_framework.linked_orders.protocols import (
    BoundedLinkIdCodec,
    ClockProtocol,
    EmulationVenue,
    GroupIdHighWaterStore,
    LinkedEventEmitter,
    LinkedGroupStore,
    LinkedOrderIdCodec,
)
from strategy_framework.linked_orders.store import InMemoryLinkedGroupStore
from strategy_framework.linked_orders.types import (
    BracketHandle,
    CancelOutcome,
    DegradedReason,
    GroupRecord,
    GroupState,
    LegFill,
    LegRecord,
    LegSnapshot,
    LegStatus,
    LinkedCancelOutcome,
    OcoHandle,
)

__all__ = [
    "LINKED_GROUP_EVENT",
    "BoundedLinkIdCodec",
    "BracketHandle",
    "CancelOutcome",
    "ClockProtocol",
    "DegradedReason",
    "EmulatedLinkedOrderManager",
    "EmulationNotEnabledError",
    "EmulationVenue",
    "GroupIdHighWaterStore",
    "GroupIdPersistenceError",
    "GroupIdSpaceExhaustedError",
    "GroupInvariantError",
    "GroupRecord",
    "GroupState",
    "InMemoryLinkedGroupStore",
    "LegFill",
    "LegRecord",
    "LegSnapshot",
    "LegStatus",
    "LinkIdCodecError",
    "LinkedCancelOutcome",
    "LinkedEventEmitter",
    "LinkedEventKind",
    "LinkedGroupEvent",
    "LinkedGroupNotFoundError",
    "LinkedGroupStore",
    "LinkedOrderError",
    "LinkedOrderIdCodec",
    "LinkedOrderManagerConfig",
    "OcoHandle",
    "RecoveryRequiredError",
    "UnsupportedLegError",
    "VolatileStoreError",
]
