"""Config field order is stable for positional callers; flag type is validated."""

from __future__ import annotations

import dataclasses

import pytest

from strategy_framework.linked_orders.config import LinkedOrderManagerConfig

PRE_EXISTING_FIELDS = [
    "enabled",
    "grace_period_s",
    "allow_volatile_store",
    "cancel_orphans",
    "group_id_seed",
    "group_id_time_factor",
    "require_recover_before_place",
    "unmatched_buffer_max",
    "tombstone_ttl_s",
    "unresolved_retry_base_s",
    "unresolved_retry_multiplier",
    "unresolved_retry_max_s",
    "understated_fill_confirmations",
]


def test_pre_existing_field_order_unchanged() -> None:
    names = [f.name for f in dataclasses.fields(LinkedOrderManagerConfig)]
    assert names[: len(PRE_EXISTING_FIELDS)] == PRE_EXISTING_FIELDS
    assert names[len(PRE_EXISTING_FIELDS) :] == ["allow_volatile_group_ids"]


@pytest.mark.parametrize("value", ["false", "yes", 1, 0, None])
def test_allow_volatile_group_ids_rejects_non_bool(value: object) -> None:
    with pytest.raises(TypeError, match="allow_volatile_group_ids"):
        LinkedOrderManagerConfig(allow_volatile_group_ids=value)  # type: ignore[arg-type]
