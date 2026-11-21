"""Configuration for the emulated linked-order manager."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class RetryBackoff:
    """Exponential schedule for `get_leg` retries of an unresolved leg (all in seconds)."""

    base_s: float = 1.0
    multiplier: float = 2.0
    max_s: float = 60.0


@dataclass(frozen=True)
class LinkedOrderManagerConfig:
    """Opt-in configuration.

    `enabled` is the explicit opt-in: the manager constructor raises when False. Emulated
    OCO cannot give native OCA guarantees: a sibling can fill before its cancel lands
    (double fill), which is detected and reported but never prevented or unwound.

    `group_id_time_factor` scales the time-derived group-id floor: `factor` ids per second since
    2026-01-01Z. The floor prevents id reuse after a restart without a persisted high-water mark
    only while sustained allocation stays below `factor` ids/s. 0 disables it. Codecs with a
    small id space (int32 userref layouts) need a small factor: the default 100 passes int32
    around mid-2026-11, while factor 1 gives about 3.15e7 ids/yr, leaving int32 headroom for
    decades before leg-index packing. Such codecs should implement `BoundedLinkIdCodec`, so the
    manager raises `GroupIdSpaceExhaustedError` rather than overflowing.
    `cancel_orphans`: attempts to cancel every unmatched leg `recover()` finds. A failing
    `cancel_leg` is logged and does not fail `recover()`, so the leg may stay live. Legs of
    another manager on the same account look like orphans, so leave it off on shared accounts.
    `require_recover_before_place`: when True, placing raises `RecoveryRequiredError` until
    `recover()` has completed successfully.
    """

    enabled: bool = False
    grace_period_s: float = 30.0
    allow_volatile_store: bool = False
    cancel_orphans: bool = False
    group_id_seed: int = 1
    group_id_time_factor: int = 100
    require_recover_before_place: bool = False
    unmatched_buffer_max: int = 1024
    tombstone_ttl_s: float = 300.0
    unresolved_retry_base_s: float = 1.0
    unresolved_retry_multiplier: float = 2.0
    unresolved_retry_max_s: float = 60.0

    def __post_init__(self) -> None:
        for name in (
            "grace_period_s",
            "unmatched_buffer_max",
            "tombstone_ttl_s",
            "unresolved_retry_base_s",
        ):
            if getattr(self, name) <= 0:
                msg = f"{name} must be > 0"
                raise ValueError(msg)
        for name in (
            "unresolved_retry_base_s",
            "unresolved_retry_multiplier",
            "unresolved_retry_max_s",
        ):
            if not math.isfinite(getattr(self, name)):
                msg = f"{name} must be finite"
                raise ValueError(msg)
        if self.unresolved_retry_multiplier < 1:
            msg = "unresolved_retry_multiplier must be >= 1"
            raise ValueError(msg)
        if self.unresolved_retry_max_s < self.unresolved_retry_base_s:
            msg = "unresolved_retry_max_s must be >= unresolved_retry_base_s"
            raise ValueError(msg)
        if self.group_id_seed < 0:
            msg = "group_id_seed must be >= 0"
            raise ValueError(msg)
        if self.group_id_time_factor < 0:
            msg = "group_id_time_factor must be >= 0"
            raise ValueError(msg)

    @property
    def retry(self) -> RetryBackoff:
        return RetryBackoff(
            self.unresolved_retry_base_s,
            self.unresolved_retry_multiplier,
            self.unresolved_retry_max_s,
        )
