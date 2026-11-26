"""Versioned JSON codec for GroupRecord."""

from __future__ import annotations

import json
from dataclasses import fields, replace
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from data_type_primitives import (
    LegRole,
    LegSpec,
    LinkedOrderSpec,
    LinkKind,
    OrderType,
    TradeType,
    TrailSpec,
    TriggerKind,
    TriggerReference,
    TriggerSpec,
)

from strategy_framework.linked_orders import (
    SCHEMA_VERSION,
    CancelOutcome,
    DegradedReason,
    GroupRecord,
    GroupRecordCodecError,
    GroupState,
    LegRecord,
    LegStatus,
    codec,
    group_id_of,
    group_record_from_dict,
    group_record_to_dict,
)
from tests.unit.linked_orders.builders import bracket_spec, oco_spec

if TYPE_CHECKING:
    from pydantic import BaseModel

D = Decimal
FIXTURE = Path(__file__).parent / "fixtures" / "group_record_v1.json"


def _leg(index: int = 0, **kw: Any) -> LegRecord:
    base: dict[str, Any] = {
        "leg_index": index,
        "role": LegRole.OCO_LEG,
        "link_tag": 7,
        "client_order_id": f"c{index}",
        "status": LegStatus.OPEN,
        "filled": D(0),
        "placed_amount": D(1),
    }
    base.update(kw)
    return LegRecord(**base)


def _record(**kw: Any) -> GroupRecord:
    base: dict[str, Any] = {
        "group_id": 1,
        "target": "BTC-USD",
        "spec": oco_spec(),
        "state": GroupState.ARMED,
        "legs": (_leg(0), _leg(1)),
    }
    base.update(kw)
    return GroupRecord(**base)


def _trailing_spec() -> LinkedOrderSpec:
    return LinkedOrderSpec(
        kind=LinkKind.OCO,
        legs=(
            LegSpec(
                role=LegRole.OCO_LEG,
                order_type=OrderType.TRAILING_STOP_LIMIT,
                trade_type=TradeType.SELL,
                amount=D("0.5"),
                limit_offset=D("-0.25"),
                trigger=TriggerSpec(
                    kind=TriggerKind.ABSOLUTE,
                    value=D("90"),
                    reference=TriggerReference.MARK,
                    trail=TrailSpec(kind=TriggerKind.PERCENT, distance=D("0.02")),
                ),
            ),
            LegSpec(
                role=LegRole.OCO_LEG,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.SELL,
                amount=D("0.5"),
                price=D("120"),
            ),
        ),
    )


def canonical_record() -> GroupRecord:
    entry = _leg(
        0,
        role=LegRole.ENTRY,
        link_tag="tag-entry",
        client_order_id="c0",
        status=LegStatus.FILLED,
        filled=D("2"),
        placed_amount=D("2"),
    )
    take_profit = _leg(
        1,
        role=LegRole.TAKE_PROFIT,
        link_tag=1001,
        client_order_id="c1",
        status=LegStatus.CANCELED,
        placed_amount=D("2"),
        cancel_requested=True,
        cancel_outcome=CancelOutcome.CANCELED,
    )
    stop_loss = _leg(
        2,
        role=LegRole.STOP_LOSS,
        link_tag=1002,
        client_order_id="c2",
        status=LegStatus.PARTIALLY_FILLED,
        filled=D("0.00000001"),
        placed_amount=D("2"),
        unresolved_since=105.5,
        retry_at=110.25,
        retry_delay_s=2.0,
        fill_reported=D("0.5"),
        fill_reports=2,
    )
    return GroupRecord(
        group_id=42,
        target="BTC-USD",
        spec=bracket_spec(),
        state=GroupState.DEGRADED,
        legs=(entry, take_profit, stop_loss),
        winner_leg_index=0,
        cancel_cause="rollback",
        degraded_reasons=frozenset({DegradedReason.LINK_BROKEN, DegradedReason.DOUBLE_FILL}),
        created_at=100.0,
    )


@pytest.fixture
def encoded() -> dict[str, Any]:
    return group_record_to_dict(canonical_record())


# -- round trips


def _roundtrip(record: GroupRecord) -> None:
    assert group_record_from_dict(group_record_to_dict(record)) == record
    wire = json.loads(json.dumps(group_record_to_dict(record)))
    assert group_record_from_dict(wire) == record


@pytest.mark.parametrize("state", list(GroupState))
def test_roundtrip_every_group_state(state: GroupState) -> None:
    _roundtrip(_record(state=state))


@pytest.mark.parametrize("status", list(LegStatus))
def test_roundtrip_every_leg_status(status: LegStatus) -> None:
    _roundtrip(_record(legs=(_leg(0, status=status), _leg(1))))


@pytest.mark.parametrize("reason", list(DegradedReason))
def test_roundtrip_each_degraded_reason(reason: DegradedReason) -> None:
    _roundtrip(_record(degraded_reasons=frozenset({reason})))


def test_roundtrip_empty_and_full_degraded_reasons() -> None:
    _roundtrip(_record(degraded_reasons=frozenset()))
    _roundtrip(_record(degraded_reasons=frozenset(DegradedReason)))


@pytest.mark.parametrize("outcome", [None, *CancelOutcome])
def test_roundtrip_cancel_outcome(outcome: CancelOutcome | None) -> None:
    _roundtrip(_record(legs=(_leg(0, cancel_outcome=outcome), _leg(1))))


@pytest.mark.parametrize("tag", [12, "12", "abc", None, 0, ""])
def test_roundtrip_link_tag_keeps_type(tag: int | str | None) -> None:
    record = _record(legs=(_leg(0, link_tag=tag), _leg(1)))
    out = group_record_from_dict(json.loads(json.dumps(group_record_to_dict(record))))
    assert out == record
    assert type(out.legs[0].link_tag) is type(tag)


@pytest.mark.parametrize("winner", [None, 0, 1])
def test_roundtrip_winner_leg_index(winner: int | None) -> None:
    _roundtrip(_record(winner_leg_index=winner))


@pytest.mark.parametrize("cause", [None, "user", "rollback"])
def test_roundtrip_cancel_cause(cause: str | None) -> None:
    _roundtrip(_record(cancel_cause=cause))


@pytest.mark.parametrize("value", [D("0.00000001"), D("123456789012345678901234567890.123456789")])
def test_roundtrip_decimal_is_exact(value: Decimal) -> None:
    record = _record(legs=(_leg(0, filled=value, placed_amount=value), _leg(1)))
    out = group_record_from_dict(json.loads(json.dumps(group_record_to_dict(record))))
    assert str(out.legs[0].filled) == str(value)
    assert out == record


@pytest.mark.parametrize("spec", [oco_spec(), oco_spec(3), bracket_spec(), _trailing_spec()])
def test_roundtrip_spec_variants(spec: LinkedOrderSpec) -> None:
    _roundtrip(_record(spec=spec))


def test_roundtrip_no_legs() -> None:
    _roundtrip(_record(legs=(), state=GroupState.PLACING))


# -- encoding shape


def test_to_dict_is_json_safe_and_versioned(encoded: dict[str, Any]) -> None:
    assert encoded["schema_version"] == SCHEMA_VERSION == 1
    assert list(encoded)[0] == "schema_version"
    assert isinstance(encoded["legs"], list)
    assert isinstance(encoded["degraded_reasons"], list)
    assert json.loads(json.dumps(encoded)) == encoded


def test_decimals_are_strings_and_enums_are_values(encoded: dict[str, Any]) -> None:
    leg = encoded["legs"][2]
    assert leg["filled"] == "1E-8"
    assert leg["placed_amount"] == "2"
    assert leg["status"] == "PARTIALLY_FILLED"
    assert leg["role"] == "stop_loss"
    assert encoded["state"] == "degraded"


def test_equal_records_give_identical_json() -> None:
    a = _record(degraded_reasons=frozenset(DegradedReason))
    b = _record(degraded_reasons=frozenset(reversed(list(DegradedReason))))
    assert a == b
    assert json.dumps(group_record_to_dict(a)) == json.dumps(group_record_to_dict(b))
    assert group_record_to_dict(a)["degraded_reasons"] == sorted(r.value for r in DegradedReason)


@pytest.mark.parametrize("group_id", [0, 1, 2, 987, 10**12])
def test_group_id_of_returns_its_own_group_id(group_id: int) -> None:
    other = _record(group_id=group_id + 1)
    record = _record(group_id=group_id)
    assert group_id_of(record) == group_id
    assert group_id_of(other) == group_id + 1
    assert group_id_of(record) != group_id_of(other)


# -- encode strictness


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("field", ["unresolved_since", "retry_at", "retry_delay_s"])
def test_encode_rejects_non_finite_leg_float(field: str, bad: float) -> None:
    record = _record(legs=(_leg(0), _leg(1, **{field: bad})))
    with pytest.raises(GroupRecordCodecError, match=rf"legs\[1\]\.{field}"):
        group_record_to_dict(record)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_encode_rejects_non_finite_created_at(bad: float) -> None:
    with pytest.raises(GroupRecordCodecError, match="created_at"):
        group_record_to_dict(_record(created_at=bad))


@pytest.mark.parametrize("bad", [D("NaN"), D("sNaN"), D("Infinity"), D("-Infinity")])
@pytest.mark.parametrize("field", ["filled", "placed_amount", "fill_reported"])
def test_encode_rejects_non_finite_leg_decimal(field: str, bad: Decimal) -> None:
    record = _record(legs=(_leg(0, **{field: bad}), _leg(1)))
    with pytest.raises(GroupRecordCodecError, match=rf"legs\[0\]\.{field}"):
        group_record_to_dict(record)


@pytest.mark.parametrize("bad", [D("NaN"), D("sNaN"), D("Infinity")])
def test_encode_rejects_non_finite_spec_decimal(bad: Decimal) -> None:
    spec = oco_spec()
    leg0 = spec.legs[0].model_construct(**{**dict(spec.legs[0]), "amount": bad})
    broken = spec.model_construct(kind=spec.kind, legs=(leg0, *spec.legs[1:]))
    with pytest.raises(GroupRecordCodecError, match=r"spec\.legs\[0\]\.amount"):
        group_record_to_dict(_record(spec=broken))


# -- strict decoding


def test_unknown_schema_version_raises_naming_version(encoded: dict[str, Any]) -> None:
    encoded["schema_version"] = 2
    with pytest.raises(GroupRecordCodecError, match="schema_version.*2"):
        group_record_from_dict(encoded)


def test_bool_schema_version_rejected(encoded: dict[str, Any]) -> None:
    encoded["schema_version"] = True
    with pytest.raises(GroupRecordCodecError, match="schema_version"):
        group_record_from_dict(encoded)


def test_error_is_value_error() -> None:
    assert issubclass(GroupRecordCodecError, ValueError)


def test_missing_field_raises(encoded: dict[str, Any]) -> None:
    del encoded["target"]
    with pytest.raises(GroupRecordCodecError, match="target"):
        group_record_from_dict(encoded)


def test_missing_nested_field_has_path(encoded: dict[str, Any]) -> None:
    del encoded["legs"][1]["status"]
    with pytest.raises(GroupRecordCodecError, match=r"legs\[1\]\.status"):
        group_record_from_dict(encoded)


def test_extra_field_raises(encoded: dict[str, Any]) -> None:
    encoded["surprise"] = 1
    with pytest.raises(GroupRecordCodecError, match="surprise"):
        group_record_from_dict(encoded)


def test_extra_nested_field_raises(encoded: dict[str, Any]) -> None:
    encoded["spec"]["legs"][0]["surprise"] = 1
    with pytest.raises(GroupRecordCodecError, match=r"spec\.legs\[0\].*surprise"):
        group_record_from_dict(encoded)


def test_bad_enum_value_raises_with_path(encoded: dict[str, Any]) -> None:
    encoded["legs"][1]["status"] = "NOPE"
    with pytest.raises(GroupRecordCodecError, match=r"legs\[1\]\.status"):
        group_record_from_dict(encoded)


def test_bad_enum_in_spec_raises_with_path(encoded: dict[str, Any]) -> None:
    encoded["spec"]["legs"][0]["order_type"] = "WARP"
    with pytest.raises(GroupRecordCodecError, match=r"spec\.legs\[0\]\.order_type"):
        group_record_from_dict(encoded)


def test_bad_degraded_reason_raises(encoded: dict[str, Any]) -> None:
    encoded["degraded_reasons"] = ["nope"]
    with pytest.raises(GroupRecordCodecError, match=r"degraded_reasons\[0\]"):
        group_record_from_dict(encoded)


def test_bad_cancel_cause_raises(encoded: dict[str, Any]) -> None:
    encoded["cancel_cause"] = "other"
    with pytest.raises(GroupRecordCodecError, match="cancel_cause"):
        group_record_from_dict(encoded)


def test_float_where_decimal_string_expected_raises(encoded: dict[str, Any]) -> None:
    encoded["legs"][0]["filled"] = 2.0
    with pytest.raises(GroupRecordCodecError, match=r"legs\[0\]\.filled"):
        group_record_from_dict(encoded)


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity", "sNaN", "abc", ""])
def test_non_finite_or_malformed_decimal_raises(encoded: dict[str, Any], bad: str) -> None:
    encoded["legs"][0]["placed_amount"] = bad
    with pytest.raises(GroupRecordCodecError, match=r"legs\[0\]\.placed_amount"):
        group_record_from_dict(encoded)


def test_bool_as_int_raises(encoded: dict[str, Any]) -> None:
    encoded["group_id"] = True
    with pytest.raises(GroupRecordCodecError, match="group_id"):
        group_record_from_dict(encoded)


def test_bool_as_link_tag_raises(encoded: dict[str, Any]) -> None:
    encoded["legs"][0]["link_tag"] = True
    with pytest.raises(GroupRecordCodecError, match=r"legs\[0\]\.link_tag"):
        group_record_from_dict(encoded)


def test_int_as_bool_raises(encoded: dict[str, Any]) -> None:
    encoded["legs"][0]["cancel_requested"] = 1
    with pytest.raises(GroupRecordCodecError, match=r"legs\[0\]\.cancel_requested"):
        group_record_from_dict(encoded)


def test_str_as_int_raises(encoded: dict[str, Any]) -> None:
    encoded["legs"][0]["leg_index"] = "0"
    with pytest.raises(GroupRecordCodecError, match=r"legs\[0\]\.leg_index"):
        group_record_from_dict(encoded)


def test_non_mapping_raises() -> None:
    with pytest.raises(GroupRecordCodecError):
        group_record_from_dict([])  # type: ignore[arg-type]


def test_legs_must_be_list(encoded: dict[str, Any]) -> None:
    encoded["legs"] = "oops"
    with pytest.raises(GroupRecordCodecError, match="legs"):
        group_record_from_dict(encoded)


def test_invalid_spec_is_wrapped(encoded: dict[str, Any]) -> None:
    encoded["spec"]["legs"][0]["amount"] = "-1"
    with pytest.raises(GroupRecordCodecError, match="spec"):
        group_record_from_dict(encoded)


def test_huge_int_for_float_field_raises_codec_error(encoded: dict[str, Any]) -> None:
    encoded["created_at"] = 10**400
    with pytest.raises(GroupRecordCodecError, match="created_at"):
        group_record_from_dict(encoded)
    encoded["created_at"] = 1.0
    encoded["legs"][2]["retry_at"] = -(10**400)
    with pytest.raises(GroupRecordCodecError, match=r"legs\[2\]\.retry_at"):
        group_record_from_dict(encoded)


def test_swapped_leg_indexes_rejected(encoded: dict[str, Any]) -> None:
    encoded["legs"][0], encoded["legs"][1] = encoded["legs"][1], encoded["legs"][0]
    with pytest.raises(GroupRecordCodecError, match=r"legs\[0\]\.leg_index.*expected 0.*got 1"):
        group_record_from_dict(encoded)


def test_duplicate_leg_index_rejected(encoded: dict[str, Any]) -> None:
    encoded["legs"][2]["leg_index"] = 1
    with pytest.raises(GroupRecordCodecError, match=r"legs\[2\]\.leg_index"):
        group_record_from_dict(encoded)


def test_replace_does_not_leak_into_encoding() -> None:
    record = canonical_record()
    changed = replace(record, target="ETH-USD")
    assert group_record_to_dict(record)["target"] == "BTC-USD"
    assert group_record_to_dict(changed)["target"] == "ETH-USD"


def test_float_field_rejects_bool(encoded: dict[str, Any]) -> None:
    encoded["created_at"] = True
    with pytest.raises(GroupRecordCodecError, match="created_at"):
        group_record_from_dict(encoded)
    encoded["created_at"] = 1.0
    encoded["legs"][2]["retry_at"] = False
    with pytest.raises(GroupRecordCodecError, match=r"legs\[2\]\.retry_at"):
        group_record_from_dict(encoded)


# -- drift guards: a field added upstream must not be silently dropped or defaulted

_DRIFT = "{name} fields changed: {diff}; update codec.py and bump SCHEMA_VERSION if incompatible"


def _assert_keys(name: str, model_keys: set[str], codec_keys: tuple[str, ...]) -> None:
    diff = sorted(model_keys ^ set(codec_keys))
    assert model_keys == set(codec_keys), _DRIFT.format(name=name, diff=diff)


@pytest.mark.parametrize(
    ("model", "keys"),
    [
        (LinkedOrderSpec, codec._SPEC_KEYS),
        (LegSpec, codec._LEG_SPEC_KEYS),
        (TriggerSpec, codec._TRIGGER_KEYS),
        (TrailSpec, codec._TRAIL_KEYS),
    ],
)
def test_pydantic_model_fields_match_codec_keys(
    model: type[BaseModel], keys: tuple[str, ...]
) -> None:
    _assert_keys(model.__name__, set(model.model_fields), keys)


@pytest.mark.parametrize(
    ("cls", "keys"),
    [(GroupRecord, codec._GROUP_KEYS), (LegRecord, codec._LEG_KEYS)],
)
def test_dataclass_fields_match_codec_keys(cls: type, keys: tuple[str, ...]) -> None:
    encoded_keys = tuple(k for k in keys if k != "schema_version")
    _assert_keys(cls.__name__, {f.name for f in fields(cls)}, encoded_keys)


def test_encoder_emits_exactly_the_declared_keys() -> None:
    top = group_record_to_dict(canonical_record())
    assert tuple(top) == codec._GROUP_KEYS
    assert tuple(top["legs"][0]) == codec._LEG_KEYS
    assert tuple(top["spec"]) == codec._SPEC_KEYS
    assert tuple(top["spec"]["legs"][0]) == codec._LEG_SPEC_KEYS
    assert tuple(top["spec"]["legs"][2]["trigger"]) == codec._TRIGGER_KEYS
    trailing = group_record_to_dict(_record(spec=_trailing_spec()))
    trail = trailing["spec"]["legs"][0]["trigger"]["trail"]
    assert tuple(trail) == codec._TRAIL_KEYS


# -- golden fixture


def test_golden_to_dict_matches_fixture() -> None:
    golden = json.loads(FIXTURE.read_text())
    assert group_record_to_dict(canonical_record()) == golden


def test_golden_from_dict_matches_canonical_record() -> None:
    golden = json.loads(FIXTURE.read_text())
    assert group_record_from_dict(golden) == canonical_record()
