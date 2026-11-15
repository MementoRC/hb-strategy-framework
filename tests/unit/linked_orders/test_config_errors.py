"""Config bounds and the error hierarchy."""

from __future__ import annotations

import dataclasses

import pytest
from data_type_primitives import LegRole, OrderType

from strategy_framework.linked_orders import (
    EmulationNotEnabledError,
    LinkedGroupNotFoundError,
    LinkedOrderError,
    LinkedOrderManagerConfig,
    LinkIdCodecError,
    UnsupportedLegError,
    VolatileStoreError,
)


def test_defaults_are_conservative() -> None:
    cfg = LinkedOrderManagerConfig()
    assert cfg.enabled is False
    assert cfg.allow_volatile_store is False
    assert cfg.cancel_orphans is False
    assert cfg.grace_period_s == 30.0
    assert cfg.unmatched_buffer_max == 1024
    assert cfg.tombstone_ttl_s == 300.0
    assert cfg.group_id_seed == 1


def test_config_is_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        LinkedOrderManagerConfig().enabled = True  # type: ignore[misc]


@pytest.mark.parametrize("field", ["grace_period_s", "unmatched_buffer_max", "tombstone_ttl_s"])
@pytest.mark.parametrize("value", [0, -1])
def test_numeric_fields_must_be_positive(field: str, value: float) -> None:
    with pytest.raises(ValueError, match=field):
        LinkedOrderManagerConfig(**{field: value})


def test_seed_may_be_zero_but_not_negative() -> None:
    assert LinkedOrderManagerConfig(group_id_seed=0).group_id_seed == 0
    with pytest.raises(ValueError, match="group_id_seed"):
        LinkedOrderManagerConfig(group_id_seed=-1)


def test_errors_share_a_root() -> None:
    errors: list[LinkedOrderError] = [
        EmulationNotEnabledError(),
        VolatileStoreError(),
        UnsupportedLegError(1, LegRole.STOP_LOSS, OrderType.STOP_LOSS),
        LinkIdCodecError(7, 2, "bad"),
        LinkedGroupNotFoundError("9"),
    ]
    assert all(isinstance(e, LinkedOrderError) for e in errors)
    assert all(str(e) for e in errors)


def test_error_payloads() -> None:
    unsupported = UnsupportedLegError(1, LegRole.STOP_LOSS, OrderType.STOP_LOSS)
    assert (unsupported.leg_index, unsupported.role, unsupported.order_type) == (
        1,
        LegRole.STOP_LOSS,
        OrderType.STOP_LOSS,
    )
    codec = LinkIdCodecError(7, 2, 99)
    assert (codec.group_id, codec.leg_index, codec.tag) == (7, 2, 99)
    assert LinkedGroupNotFoundError("9").group_id == "9"
