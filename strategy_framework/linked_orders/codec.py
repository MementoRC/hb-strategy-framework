"""Versioned, JSON-safe codec for `GroupRecord`.

External durable stores inject `group_record_to_dict`, `group_record_from_dict` and
`group_id_of`. The wire form uses only JSON primitives:

- `Decimal` -> `str` (exact, never float); decoding requires a finite decimal string.
- Enums -> `.value` when it is a string. `OrderType` and `TradeType` have int values that are
  unreadable and renumber-prone, so they use `.name`. One rule, applied to every enum.
- `tuple` -> list; `frozenset` -> list sorted by the encoded value.
- Nested dataclasses and the data-type-primitives specs -> dicts in declared field order, so
  `json.dumps` output is stable. The specs are encoded here (not with pydantic dumping) so that
  decoding stays strict: no coercion of floats, bools or numeric strings.

Decoding is strict: wrong `schema_version`, missing or unknown keys, wrong types and bad enum
values raise `GroupRecordCodecError` carrying a field path such as `legs[1].status`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal, InvalidOperation
from enum import Enum
from math import isfinite
from typing import Any, Literal, NoReturn, cast

from data_type_primitives import (
    CancelOutcome,
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

from strategy_framework.linked_orders.errors import LinkedOrderError
from strategy_framework.linked_orders.types import (
    DegradedReason,
    GroupId,
    GroupRecord,
    GroupState,
    LegRecord,
    LegStatus,
    LinkTag,
)

SCHEMA_VERSION = 1
"""Bump on any incompatible change to the wire form and add a migration in the decoder."""

_CANCEL_CAUSES: tuple[Literal["user", "rollback"], ...] = ("user", "rollback")

_GROUP_KEYS = (
    "schema_version",
    "group_id",
    "target",
    "spec",
    "state",
    "legs",
    "winner_leg_index",
    "cancel_cause",
    "degraded_reasons",
    "created_at",
)
_LEG_KEYS = (
    "leg_index",
    "role",
    "link_tag",
    "client_order_id",
    "status",
    "filled",
    "placed_amount",
    "cancel_requested",
    "cancel_outcome",
    "unresolved_since",
    "retry_at",
    "retry_delay_s",
    "fill_reported",
    "fill_reports",
)
_SPEC_KEYS = ("kind", "legs")
_LEG_SPEC_KEYS = (
    "role",
    "order_type",
    "trade_type",
    "amount",
    "price",
    "trigger",
    "limit_offset",
)
_TRIGGER_KEYS = ("kind", "value", "reference", "trail")
_TRAIL_KEYS = ("kind", "distance")


class GroupRecordCodecError(LinkedOrderError, ValueError):
    """A `GroupRecord` could not be encoded or decoded (message carries the field path)."""


def group_id_of(record: GroupRecord) -> GroupId:
    """The store key of `record`."""
    return record.group_id


# -- encoding


def _enc_enum(member: Enum) -> str:
    # str values are used as is; int values (OrderType, TradeType) are encoded by name.
    return member.value if isinstance(member.value, str) else member.name


def _enc_opt[T](value: T | None, fn: Callable[[T], Any]) -> Any:
    return None if value is None else fn(value)


def _enc_trail(trail: TrailSpec) -> dict[str, Any]:
    return {"kind": _enc_enum(trail.kind), "distance": str(trail.distance)}


def _enc_trigger(trigger: TriggerSpec) -> dict[str, Any]:
    return {
        "kind": _enc_enum(trigger.kind),
        "value": str(trigger.value),
        "reference": _enc_enum(trigger.reference),
        "trail": _enc_opt(trigger.trail, _enc_trail),
    }


def _enc_leg_spec(leg: LegSpec) -> dict[str, Any]:
    return {
        "role": _enc_enum(leg.role),
        "order_type": _enc_enum(leg.order_type),
        "trade_type": _enc_enum(leg.trade_type),
        "amount": str(leg.amount),
        "price": _enc_opt(leg.price, str),
        "trigger": _enc_opt(leg.trigger, _enc_trigger),
        "limit_offset": _enc_opt(leg.limit_offset, str),
    }


def _enc_spec(spec: LinkedOrderSpec) -> dict[str, Any]:
    return {"kind": _enc_enum(spec.kind), "legs": [_enc_leg_spec(leg) for leg in spec.legs]}


def _enc_leg(leg: LegRecord) -> dict[str, Any]:
    return {
        "leg_index": leg.leg_index,
        "role": _enc_enum(leg.role),
        "link_tag": leg.link_tag,
        "client_order_id": leg.client_order_id,
        "status": _enc_enum(leg.status),
        "filled": str(leg.filled),
        "placed_amount": str(leg.placed_amount),
        "cancel_requested": leg.cancel_requested,
        "cancel_outcome": _enc_opt(leg.cancel_outcome, _enc_enum),
        "unresolved_since": leg.unresolved_since,
        "retry_at": leg.retry_at,
        "retry_delay_s": leg.retry_delay_s,
        "fill_reported": _enc_opt(leg.fill_reported, str),
        "fill_reports": leg.fill_reports,
    }


def group_record_to_dict(record: GroupRecord) -> dict[str, Any]:
    """Encode `record` as a JSON-safe dict (see the module docstring for the rules)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "group_id": record.group_id,
        "target": record.target,
        "spec": _enc_spec(record.spec),
        "state": _enc_enum(record.state),
        "legs": [_enc_leg(leg) for leg in record.legs],
        "winner_leg_index": record.winner_leg_index,
        "cancel_cause": record.cancel_cause,
        "degraded_reasons": sorted(_enc_enum(r) for r in record.degraded_reasons),
        "created_at": record.created_at,
    }


# -- decoding primitives


def _fail(path: str, message: str) -> NoReturn:
    raise GroupRecordCodecError(f"{path}: {message}" if path else message)


def _join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _obj(data: object, path: str, keys: tuple[str, ...]) -> Mapping[str, Any]:
    if not isinstance(data, Mapping):
        _fail(path, f"expected an object, got {type(data).__name__}")
    missing = [k for k in keys if k not in data]
    if missing:
        _fail(_join(path, missing[0]), f"missing field (all missing: {missing})")
    unknown = sorted(str(k) for k in data if k not in keys)
    if unknown:
        _fail(path, f"unknown field(s) {unknown}")
    return data


def _list(data: object, path: str) -> list[Any]:
    if not isinstance(data, list):
        _fail(path, f"expected a list, got {type(data).__name__}")
    return data


def _int(value: object, path: str) -> int:
    if type(value) is not int:
        _fail(path, f"expected an int, got {type(value).__name__}")
    return value


def _str(value: object, path: str) -> str:
    if not isinstance(value, str):
        _fail(path, f"expected a string, got {type(value).__name__}")
    return value


def _bool(value: object, path: str) -> bool:
    if not isinstance(value, bool):
        _fail(path, f"expected a bool, got {type(value).__name__}")
    return value


def _float(value: object, path: str) -> float:
    if type(value) not in (int, float):
        _fail(path, f"expected a number, got {type(value).__name__}")
    result = float(cast("float", value))
    if not isfinite(result):
        _fail(path, "expected a finite number")
    return result


def _dec(value: object, path: str) -> Decimal:
    if not isinstance(value, str):
        _fail(path, f"expected a decimal string, got {type(value).__name__}")
    try:
        result = Decimal(value)
    except InvalidOperation:
        _fail(path, f"invalid decimal string {value!r}")
    if not result.is_finite():
        _fail(path, f"decimal must be finite, got {value!r}")
    return result


def _enum[E: Enum](cls: type[E], value: object, path: str) -> E:
    for member in cls:
        if _enc_enum(member) == value:
            return member
    _fail(path, f"invalid {cls.__name__} {value!r}")


def _opt[T](value: object, path: str, fn: Callable[[Any, str], T]) -> T | None:
    return None if value is None else fn(value, path)


def _link_tag(value: object, path: str) -> LinkTag | None:
    if value is None or isinstance(value, str):
        return value
    return _int(value, path)


# -- decoding structures


def _dec_trail(data: object, path: str) -> TrailSpec:
    obj = _obj(data, path, _TRAIL_KEYS)
    return _build(
        path,
        TrailSpec,
        kind=_enum(TriggerKind, obj["kind"], _join(path, "kind")),
        distance=_dec(obj["distance"], _join(path, "distance")),
    )


def _dec_trigger(data: object, path: str) -> TriggerSpec:
    obj = _obj(data, path, _TRIGGER_KEYS)
    return _build(
        path,
        TriggerSpec,
        kind=_enum(TriggerKind, obj["kind"], _join(path, "kind")),
        value=_dec(obj["value"], _join(path, "value")),
        reference=_enum(TriggerReference, obj["reference"], _join(path, "reference")),
        trail=_opt(obj["trail"], _join(path, "trail"), _dec_trail),
    )


def _dec_leg_spec(data: object, path: str) -> LegSpec:
    obj = _obj(data, path, _LEG_SPEC_KEYS)
    return _build(
        path,
        LegSpec,
        role=_enum(LegRole, obj["role"], _join(path, "role")),
        order_type=_enum(OrderType, obj["order_type"], _join(path, "order_type")),
        trade_type=_enum(TradeType, obj["trade_type"], _join(path, "trade_type")),
        amount=_dec(obj["amount"], _join(path, "amount")),
        price=_opt(obj["price"], _join(path, "price"), _dec),
        trigger=_opt(obj["trigger"], _join(path, "trigger"), _dec_trigger),
        limit_offset=_opt(obj["limit_offset"], _join(path, "limit_offset"), _dec),
    )


def _dec_spec(data: object, path: str) -> LinkedOrderSpec:
    obj = _obj(data, path, _SPEC_KEYS)
    legs_path = _join(path, "legs")
    legs = tuple(
        _dec_leg_spec(item, f"{legs_path}[{i}]")
        for i, item in enumerate(_list(obj["legs"], legs_path))
    )
    kind = _enum(LinkKind, obj["kind"], _join(path, "kind"))
    return _build(path, LinkedOrderSpec, kind=kind, legs=legs)


def _build[T](path: str, cls: Callable[..., T], **kwargs: Any) -> T:
    """Construct a validated model/dataclass, reporting its own ValueErrors with the path."""
    try:
        return cls(**kwargs)
    except ValueError as exc:
        _fail(path, f"invalid value: {exc}")


def _dec_leg(data: object, path: str) -> LegRecord:
    obj = _obj(data, path, _LEG_KEYS)

    def at(key: str) -> str:
        return _join(path, key)

    client_order_id = obj["client_order_id"]
    return LegRecord(
        leg_index=_int(obj["leg_index"], at("leg_index")),
        role=_enum(LegRole, obj["role"], at("role")),
        link_tag=_link_tag(obj["link_tag"], at("link_tag")),
        client_order_id=_opt(client_order_id, at("client_order_id"), _str),
        status=_enum(LegStatus, obj["status"], at("status")),
        filled=_dec(obj["filled"], at("filled")),
        placed_amount=_dec(obj["placed_amount"], at("placed_amount")),
        cancel_requested=_bool(obj["cancel_requested"], at("cancel_requested")),
        cancel_outcome=_opt(
            obj["cancel_outcome"],
            at("cancel_outcome"),
            lambda v, p: _enum(CancelOutcome, v, p),
        ),
        unresolved_since=_opt(obj["unresolved_since"], at("unresolved_since"), _float),
        retry_at=_opt(obj["retry_at"], at("retry_at"), _float),
        retry_delay_s=_opt(obj["retry_delay_s"], at("retry_delay_s"), _float),
        fill_reported=_opt(obj["fill_reported"], at("fill_reported"), _dec),
        fill_reports=_int(obj["fill_reports"], at("fill_reports")),
    )


def _dec_cancel_cause(value: object, path: str) -> Literal["user", "rollback"] | None:
    for cause in _CANCEL_CAUSES:
        if value == cause:
            return cause
    if value is None:
        return None
    return _fail(path, f"invalid cancel_cause {value!r}")


def _check_version(data: object) -> None:
    if isinstance(data, Mapping) and "schema_version" in data:
        version = data["schema_version"]
        if type(version) is not int or version != SCHEMA_VERSION:
            _fail("schema_version", f"unsupported version {version!r}, expected {SCHEMA_VERSION}")


def group_record_from_dict(data: Mapping[str, Any]) -> GroupRecord:
    """Decode the output of `group_record_to_dict` (strict; raises `GroupRecordCodecError`)."""
    _check_version(data)
    obj = _obj(data, "", _GROUP_KEYS)
    legs = tuple(_dec_leg(item, f"legs[{i}]") for i, item in enumerate(_list(obj["legs"], "legs")))
    reasons = frozenset(
        _enum(DegradedReason, item, f"degraded_reasons[{i}]")
        for i, item in enumerate(_list(obj["degraded_reasons"], "degraded_reasons"))
    )
    return GroupRecord(
        group_id=_int(obj["group_id"], "group_id"),
        target=_str(obj["target"], "target"),
        spec=_dec_spec(obj["spec"], "spec"),
        state=_enum(GroupState, obj["state"], "state"),
        legs=legs,
        winner_leg_index=_opt(obj["winner_leg_index"], "winner_leg_index", _int),
        cancel_cause=_dec_cancel_cause(obj["cancel_cause"], "cancel_cause"),
        degraded_reasons=reasons,
        created_at=_float(obj["created_at"], "created_at"),
    )
