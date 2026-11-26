"""Value types for the emulated linked-order manager (pure data, no I/O)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Literal

from data_type_primitives import CancelOutcome as CancelOutcome  # noqa: PLC0414  (re-export)
from data_type_primitives import LinkedCancelOutcome as _DtpLinkedCancelOutcome

if TYPE_CHECKING:
    from decimal import Decimal

    from data_type_primitives import LegRole, LinkedOrderSpec, OrderState

GroupId = int
"""Internal group id; an int so int32 userref layouts (Kraken) can encode it.

int32 layouts need a reduced `group_id_time_factor` (the default 100 outgrows int32 within a
year) and should implement `BoundedLinkIdCodec` so overflow fails loudly.
"""

LinkTag = str | int
"""What the venue attaches to an order (client_order_id or userref)."""


class GroupState(Enum):
    """Lifecycle state of a linked group."""

    PLACING = "placing"
    ENTRY_WORKING = "entry_working"
    EXITS_PLACING = "exits_placing"
    ARMED = "armed"
    TRIGGERED = "triggered"
    CANCELLING = "cancelling"
    COMPLETED = "completed"
    CANCELED = "canceled"
    FAILED = "failed"
    DEGRADED = "degraded"


OUTCOME_STATES = frozenset({GroupState.COMPLETED, GroupState.CANCELED, GroupState.FAILED})
"""Outcome states; they can only move on to DEGRADED."""

PLACEMENT_STATES = frozenset(
    {GroupState.PLACING, GroupState.ENTRY_WORKING, GroupState.EXITS_PLACING}
)
"""States in which legs may still be submitted (ENTRY_WORKING waits for the entry)."""


class LegStatus(Enum):
    """`OrderState` members plus the local NOT_PLACED (never submitted)."""

    PENDING_CREATE = "PENDING_CREATE"
    OPEN = "OPEN"
    PENDING_CANCEL = "PENDING_CANCEL"
    CANCELED = "CANCELED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    FAILED = "FAILED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    CREATED = "CREATED"
    COMPLETED = "COMPLETED"
    UNKNOWN = "UNKNOWN"
    NOT_PLACED = "NOT_PLACED"

    @classmethod
    def from_order_state(cls, state: OrderState) -> LegStatus:
        return cls[state.name]


TERMINAL_STATUSES = frozenset(
    {
        LegStatus.FILLED,
        LegStatus.CANCELED,
        LegStatus.FAILED,
        LegStatus.COMPLETED,
        LegStatus.NOT_PLACED,
    }
)


class DegradedReason(Enum):
    """Why a group went DEGRADED (each reason emits exactly one event per group)."""

    DOUBLE_FILL = "double_fill"
    UNRESOLVED_PAST_GRACE = "unresolved_past_grace"
    EXIT_PLACEMENT_FAILED = "exit_placement_failed"
    LINK_BROKEN = "link_broken"


@dataclass(frozen=True)
class LegSnapshot:
    """Venue view of one leg. `filled` is cumulative."""

    client_order_id: str
    link_tag: LinkTag | None
    state: OrderState
    filled: Decimal


@dataclass(frozen=True)
class LegFill:
    """A (cumulative) fill report for one leg."""

    client_order_id: str
    cumulative_filled: Decimal
    last_price: Decimal
    timestamp: float
    fill_id: str | None = None


@dataclass(frozen=True)
class LegRecord:
    """Persisted state of one submitted (or NOT_PLACED) leg.

    `link_tag` is None only for NOT_PLACED legs, which never reached the venue.
    """

    leg_index: int
    role: LegRole
    link_tag: LinkTag | None
    client_order_id: str | None
    status: LegStatus
    filled: Decimal
    placed_amount: Decimal
    cancel_requested: bool = False
    cancel_outcome: CancelOutcome | None = None
    unresolved_since: float | None = None
    # Transient get_leg backoff state: never a persist trigger, cleared on load and on resolution.
    retry_at: float | None = None
    retry_delay_s: float | None = None
    # Transient understated-fill tracking (same lifecycle as the retry state): the filled value
    # the venue keeps reporting as FILLED while below placed_amount, and how often it did.
    fill_reported: Decimal | None = None
    fill_reports: int = 0


@dataclass(frozen=True)
class GroupRecord:
    """Persisted state of one linked group. `legs[i].leg_index == i` always."""

    group_id: GroupId
    target: str
    spec: LinkedOrderSpec
    state: GroupState
    legs: tuple[LegRecord, ...] = ()
    winner_leg_index: int | None = None
    cancel_cause: Literal["user", "rollback"] | None = None
    degraded_reasons: frozenset[DegradedReason] = field(default_factory=frozenset)
    created_at: float = 0.0


@dataclass(frozen=True)
class OcoHandle:
    """Snapshot handle for an OCO group. Check `state` after `place_oco`."""

    group_id: str
    leg_client_order_ids: tuple[str | None, ...]
    state: GroupState
    emulated: bool = True


@dataclass(frozen=True)
class BracketHandle:
    """Snapshot handle for a BRACKET group. Check `state` after `place_bracket`."""

    group_id: str
    entry_client_order_id: str | None
    take_profit_client_order_id: str | None
    stop_loss_client_order_id: str | None
    state: GroupState
    emulated: bool = True


class LinkedCancelOutcome(_DtpLinkedCancelOutcome):
    """Result of `cancel_linked`: the dtp outcome plus the group's final `GroupState`."""

    state: GroupState
