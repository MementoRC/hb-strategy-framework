"""Configuration for the emulated linked-order manager."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LinkedOrderManagerConfig:
    """Opt-in configuration.

    `enabled` is the explicit opt-in: the manager constructor raises when False. Emulated
    OCO cannot give native OCA guarantees: a sibling can fill before its cancel lands
    (double fill), which is detected and reported but never prevented or unwound.

    `group_id_time_factor` scales the time-derived group-id floor (0 disables it).
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

    def __post_init__(self) -> None:
        for name in ("grace_period_s", "unmatched_buffer_max", "tombstone_ttl_s"):
            if getattr(self, name) <= 0:
                msg = f"{name} must be > 0"
                raise ValueError(msg)
        if self.group_id_seed < 0:
            msg = "group_id_seed must be >= 0"
            raise ValueError(msg)
        if self.group_id_time_factor < 0:
            msg = "group_id_time_factor must be >= 0"
            raise ValueError(msg)
