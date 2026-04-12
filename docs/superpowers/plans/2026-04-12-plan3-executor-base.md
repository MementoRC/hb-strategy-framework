# Plan 3: ExecutorBase & TripleBarrierExecutor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `strategy_framework/executors/` with an event-driven `ExecutorBase` (state machine + layered event model) and a `TripleBarrierExecutor` that assembles four Plan 2 mixins into a complete, testable trading unit.

**Architecture:** Approach A — `ExecutorBase` owns a validated `IDLE→ACTIVE→CLOSING→CLOSED` state machine, 6 dedicated event hooks (guaranteed first-class delivery), and an internal `EventBus` for secondary handlers. `TripleBarrierExecutor` inherits `ExecutorBase` + `ActivationBoundsMixin` + `OrderTrackingMixin` + `PNLCalculatorMixin` + `TrailingStopMixin`. `ExecutorConfigBase` (extends `StrategyConfigBase`) namespaces executor configs. Time-limit exits driven by `tick(now: datetime)` called from `on_price_updated`.

**Tech Stack:** Python 3.10+, Pydantic v2, mypy strict, ruff, pytest (asyncio_mode=auto), pixi.

**Working directory for all commands:** `sub-packages/strategy-framework/.worktrees/feat-executor-mixins/`

**Spec:** `docs/superpowers/specs/2026-04-12-plan3-executor-base-design.md`

---

## File Map

### Create
- `strategy_framework/executors/__init__.py` — public re-exports
- `strategy_framework/executors/base.py` — `ExecutorConfigBase`, `ExecutorState`, `ExecutorStateError`, `ExecutorBase`
- `strategy_framework/executors/events.py` — `EventBus`, typed event dataclasses
- `strategy_framework/executors/triple_barrier.py` — `TripleBarrierExecutorConfig`, `TripleBarrierExecutor`
- `tests/unit/executors/__init__.py`
- `tests/unit/executors/test_base.py`
- `tests/unit/executors/test_events.py`
- `tests/unit/executors/test_triple_barrier.py`
- `tests/integration/test_executor_lifecycle.py`

### Modify
- `strategy_framework/__init__.py` — add executor exports
- `tests/integration/__init__.py` — ensure exists (may already)

---

## Task 1: ExecutorState + ExecutorStateError

**Files:**
- Create: `strategy_framework/executors/base.py` (state enum + error only)
- Create: `tests/unit/executors/__init__.py`
- Create: `tests/unit/executors/test_base.py` (state tests only)

- [ ] **Step 1.1: Create test file with state machine tests**

```python
# tests/unit/executors/test_base.py
from __future__ import annotations

import pytest
from strategy_framework.executors.base import ExecutorState, ExecutorStateError


class TestExecutorState:
    def test_states_exist(self) -> None:
        assert ExecutorState.IDLE
        assert ExecutorState.ACTIVE
        assert ExecutorState.CLOSING
        assert ExecutorState.CLOSED

    def test_state_error_is_exception(self) -> None:
        err = ExecutorStateError("bad transition")
        assert isinstance(err, Exception)
        assert "bad transition" in str(err)
```

- [ ] **Step 1.2: Run to verify failure**

```
pixi run pytest tests/unit/executors/test_base.py -v
```
Expected: `ModuleNotFoundError` or `ImportError`

- [ ] **Step 1.3: Create module scaffold**

```python
# strategy_framework/executors/__init__.py
"""Executor layer — ExecutorBase and concrete executor implementations."""
```

```python
# tests/unit/executors/__init__.py
```

- [ ] **Step 1.4: Implement ExecutorState + ExecutorStateError**

```python
# strategy_framework/executors/base.py
from __future__ import annotations

from enum import Enum, auto


class ExecutorState(Enum):
    IDLE = auto()
    ACTIVE = auto()
    CLOSING = auto()
    CLOSED = auto()


class ExecutorStateError(Exception):
    """Raised when an invalid state transition is attempted."""
```

- [ ] **Step 1.5: Run tests**

```
pixi run pytest tests/unit/executors/test_base.py -v
```
Expected: 2 PASSED

- [ ] **Step 1.6: Commit**

```
git add strategy_framework/executors/ tests/unit/executors/
git commit -m "feat(executors): scaffold module with ExecutorState and ExecutorStateError"
```

---

## Task 2: EventBus + Typed Event Dataclasses

**Files:**
- Create: `strategy_framework/executors/events.py`
- Create: `tests/unit/executors/test_events.py`

- [ ] **Step 2.1: Write failing tests for EventBus**

```python
# tests/unit/executors/test_events.py
from __future__ import annotations

from decimal import Decimal

import pytest
from strategy_framework.executors.events import (
    EventBus,
    OrderCancelledEvent,
    OrderFailedEvent,
    OrderFilledEvent,
    PriceUpdatedEvent,
)


class TestEventDataclasses:
    def test_order_filled_event_is_frozen(self) -> None:
        evt = OrderFilledEvent(order_id="o1", price=Decimal("100"), amount=Decimal("1"))
        with pytest.raises((AttributeError, TypeError)):
            evt.order_id = "other"  # type: ignore[misc]

    def test_price_updated_event(self) -> None:
        evt = PriceUpdatedEvent(price=Decimal("50000"))
        assert evt.price == Decimal("50000")

    def test_order_cancelled_event(self) -> None:
        evt = OrderCancelledEvent(order_id="o2")
        assert evt.order_id == "o2"

    def test_order_failed_event(self) -> None:
        evt = OrderFailedEvent(order_id="o3", reason="timeout")
        assert evt.reason == "timeout"


class TestEventBus:
    def test_subscribe_and_emit(self) -> None:
        bus = EventBus()
        received: list[OrderFilledEvent] = []
        bus.subscribe("order.filled", received.append)
        evt = OrderFilledEvent(order_id="o1", price=Decimal("100"), amount=Decimal("1"))
        bus.emit("order.filled", evt)
        assert received == [evt]

    def test_unsubscribe(self) -> None:
        bus = EventBus()
        received: list[object] = []
        handler = received.append
        bus.subscribe("order.filled", handler)
        bus.unsubscribe("order.filled", handler)
        bus.emit("order.filled", OrderFilledEvent("o1", Decimal("1"), Decimal("1")))
        assert received == []

    def test_multiple_handlers_called_in_order(self) -> None:
        bus = EventBus()
        order: list[str] = []
        bus.subscribe("ev", lambda _: order.append("first"))
        bus.subscribe("ev", lambda _: order.append("second"))
        bus.emit("ev", "payload")
        assert order == ["first", "second"]

    def test_handler_exception_does_not_stop_others(self) -> None:
        bus = EventBus()
        reached: list[bool] = []

        def bad_handler(_: object) -> None:
            raise RuntimeError("boom")

        bus.subscribe("ev", bad_handler)
        bus.subscribe("ev", lambda _: reached.append(True))
        bus.emit("ev", "payload")  # must not raise
        assert reached == [True]

    def test_emit_unknown_event_type_is_noop(self) -> None:
        bus = EventBus()
        bus.emit("no.subscribers", "payload")  # must not raise

    def test_unsubscribe_nonexistent_handler_is_noop(self) -> None:
        bus = EventBus()
        bus.unsubscribe("ev", lambda _: None)  # must not raise
```

- [ ] **Step 2.2: Run to verify failure**

```
pixi run pytest tests/unit/executors/test_events.py -v
```
Expected: `ImportError`

- [ ] **Step 2.3: Implement events.py**

```python
# strategy_framework/executors/events.py
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OrderFilledEvent:
    order_id: str
    price: Decimal
    amount: Decimal


@dataclass(frozen=True)
class OrderCancelledEvent:
    order_id: str


@dataclass(frozen=True)
class OrderFailedEvent:
    order_id: str
    reason: str


@dataclass(frozen=True)
class PriceUpdatedEvent:
    price: Decimal


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[[Any], None]]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Callable[[Any], None]) -> None:
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable[[Any], None]) -> None:
        handlers = self._handlers.get(event_type, [])
        try:
            handlers.remove(handler)
        except ValueError:
            pass

    def emit(self, event_type: str, event: Any) -> None:
        for handler in list(self._handlers.get(event_type, [])):
            try:
                handler(event)
            except Exception:
                logger.exception("EventBus handler raised for event type %r", event_type)
```

- [ ] **Step 2.4: Run tests**

```
pixi run pytest tests/unit/executors/test_events.py -v
```
Expected: 10 PASSED

- [ ] **Step 2.5: Commit**

```
git add strategy_framework/executors/events.py tests/unit/executors/test_events.py
git commit -m "feat(executors): add EventBus with typed event dataclasses"
```

---

## Task 3: ExecutorConfigBase + ExecutorBase (state machine + hooks)

**Files:**
- Modify: `strategy_framework/executors/base.py` — add ExecutorConfigBase, ExecutorBase
- Modify: `tests/unit/executors/test_base.py` — add ExecutorBase tests

- [ ] **Step 3.1: Add ExecutorBase tests**

Append to `tests/unit/executors/test_base.py`:

```python
from __future__ import annotations

from decimal import Decimal

import pytest
from strategy_framework.config.base import StrategyConfigBase
from strategy_framework.executors.base import (
    ExecutorBase,
    ExecutorConfigBase,
    ExecutorState,
    ExecutorStateError,
)
from strategy_framework.primitives.enums import CloseType
from strategy_framework.testing.mock_market import MockMarketAccess


class ConcreteConfig(ExecutorConfigBase):
    pass


class ConcreteExecutor(ExecutorBase):
    started_count: int = 0
    stopped_args: list[CloseType] = []

    def on_started(self) -> None:
        self.started_count += 1

    def on_stopped(self, close_type: CloseType) -> None:
        self.stopped_args.append(close_type)


def make_executor() -> ConcreteExecutor:
    market = MockMarketAccess()
    config = ConcreteConfig()
    return ConcreteExecutor(market=market, config=config)


class TestExecutorConfigBase:
    def test_is_strategy_config_base(self) -> None:
        config = ConcreteConfig()
        assert isinstance(config, StrategyConfigBase)


class TestExecutorBaseStateMachine:
    def test_initial_state_is_idle(self) -> None:
        ex = make_executor()
        assert ex.state == ExecutorState.IDLE

    def test_start_transitions_to_active(self) -> None:
        ex = make_executor()
        ex.start()
        assert ex.state == ExecutorState.ACTIVE

    def test_start_calls_on_started(self) -> None:
        ex = make_executor()
        ex.start()
        assert ex.started_count == 1

    def test_stop_from_active_transitions_to_closed(self) -> None:
        ex = make_executor()
        ex.start()
        ex.stop(CloseType.TAKE_PROFIT)
        assert ex.state == ExecutorState.CLOSED

    def test_stop_calls_on_stopped_with_close_type(self) -> None:
        ex = make_executor()
        ex.start()
        ex.stop(CloseType.STOP_LOSS)
        assert ex.stopped_args == [CloseType.STOP_LOSS]

    def test_double_stop_is_noop(self) -> None:
        ex = make_executor()
        ex.start()
        ex.stop(CloseType.TAKE_PROFIT)
        ex.stop(CloseType.TAKE_PROFIT)  # must not raise, still CLOSED
        assert ex.state == ExecutorState.CLOSED
        assert len(ex.stopped_args) == 1

    def test_invalid_transition_raises(self) -> None:
        ex = make_executor()
        with pytest.raises(ExecutorStateError):
            ex.stop(CloseType.TAKE_PROFIT)  # cannot stop from IDLE

    def test_state_is_read_only(self) -> None:
        ex = make_executor()
        with pytest.raises(AttributeError):
            ex.state = ExecutorState.CLOSED  # type: ignore[misc]


class TestExecutorBaseHooksFireBeforeBus:
    def test_hook_fires_before_bus_handler(self) -> None:
        order: list[str] = []
        market = MockMarketAccess()

        class TrackingExecutor(ExecutorBase):
            def on_order_filled(self, order_id: str, price: Decimal, amount: Decimal) -> None:
                order.append("hook")

        ex = TrackingExecutor(market=market, config=ConcreteConfig())
        ex.bus.subscribe("order.filled", lambda _: order.append("bus"))
        ex.start()
        ex.notify_order_filled("o1", Decimal("100"), Decimal("1"))
        assert order == ["hook", "bus"]
```

- [ ] **Step 3.2: Run to verify failure**

```
pixi run pytest tests/unit/executors/test_base.py -v
```
Expected: failures (ExecutorBase not yet implemented)

- [ ] **Step 3.3: Implement ExecutorConfigBase + ExecutorBase**

Replace contents of `strategy_framework/executors/base.py`:

```python
# strategy_framework/executors/base.py
from __future__ import annotations

from decimal import Decimal
from enum import Enum, auto
from typing import TYPE_CHECKING

from strategy_framework.config.base import StrategyConfigBase
from strategy_framework.executors.events import (
    EventBus,
    OrderCancelledEvent,
    OrderFailedEvent,
    OrderFilledEvent,
    PriceUpdatedEvent,
)
from strategy_framework.primitives.enums import CloseType

if TYPE_CHECKING:
    import datetime

    from strategy_framework.protocols.market import MarketAccessProtocol


class ExecutorState(Enum):
    IDLE = auto()
    ACTIVE = auto()
    CLOSING = auto()
    CLOSED = auto()


class ExecutorStateError(Exception):
    """Raised on invalid state transition."""


class ExecutorConfigBase(StrategyConfigBase):
    """Base config for all executor types."""


_VALID_TRANSITIONS: frozenset[tuple[ExecutorState, ExecutorState]] = frozenset({
    (ExecutorState.IDLE, ExecutorState.ACTIVE),
    (ExecutorState.ACTIVE, ExecutorState.CLOSING),
    (ExecutorState.CLOSING, ExecutorState.CLOSED),
})


class ExecutorBase:
    def __init__(
        self,
        market: MarketAccessProtocol,
        config: ExecutorConfigBase,
        bus: EventBus | None = None,
    ) -> None:
        self._market = market
        self._config = config
        self._state = ExecutorState.IDLE
        self.bus: EventBus = bus if bus is not None else EventBus()

    @property
    def state(self) -> ExecutorState:
        return self._state

    def _transition(self, target: ExecutorState) -> None:
        if (self._state, target) not in _VALID_TRANSITIONS:
            raise ExecutorStateError(
                f"Invalid transition: {self._state.name} → {target.name}"
            )
        self._state = target

    # ------------------------------------------------------------------ #
    # Public lifecycle                                                      #
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        self._transition(ExecutorState.ACTIVE)
        self.on_started()

    def stop(self, close_type: CloseType) -> None:
        if self._state == ExecutorState.CLOSED:
            return  # double-stop guard
        self._transition(ExecutorState.CLOSING)
        self._transition(ExecutorState.CLOSED)
        self.on_stopped(close_type)

    def tick(self, now: datetime.datetime) -> None:
        """Drive time-based checks (e.g. time-limit exit). Call from on_price_updated or Controller heartbeat."""

    # ------------------------------------------------------------------ #
    # Notify methods — called by external driver (Controller / test)       #
    # ------------------------------------------------------------------ #

    def notify_order_filled(self, order_id: str, price: Decimal, amount: Decimal) -> None:
        self.on_order_filled(order_id, price, amount)
        self.bus.emit("order.filled", OrderFilledEvent(order_id, price, amount))

    def notify_order_cancelled(self, order_id: str) -> None:
        self.on_order_cancelled(order_id)
        self.bus.emit("order.cancelled", OrderCancelledEvent(order_id))

    def notify_order_failed(self, order_id: str, reason: str) -> None:
        self.on_order_failed(order_id, reason)
        self.bus.emit("order.failed", OrderFailedEvent(order_id, reason))

    def notify_price_updated(self, price: Decimal) -> None:
        self.on_price_updated(price)
        self.bus.emit("price.updated", PriceUpdatedEvent(price))

    # ------------------------------------------------------------------ #
    # Dedicated event hooks — override in subclasses                       #
    # ------------------------------------------------------------------ #

    def on_started(self) -> None:
        pass

    def on_stopped(self, close_type: CloseType) -> None:
        pass

    def on_order_filled(self, order_id: str, price: Decimal, amount: Decimal) -> None:
        pass

    def on_order_cancelled(self, order_id: str) -> None:
        pass

    def on_order_failed(self, order_id: str, reason: str) -> None:
        pass

    def on_price_updated(self, price: Decimal) -> None:
        pass
```

- [ ] **Step 3.4: Run tests**

```
pixi run pytest tests/unit/executors/test_base.py -v
```
Expected: all PASSED

- [ ] **Step 3.5: Run full suite to check no regressions**

```
pixi run test
```
Expected: all PASSED (151 + new)

- [ ] **Step 3.6: Commit**

```
git add strategy_framework/executors/base.py tests/unit/executors/test_base.py
git commit -m "feat(executors): implement ExecutorBase with state machine, hooks, and EventBus wiring"
```

---

## Task 4: TripleBarrierExecutorConfig

**Files:**
- Create: `strategy_framework/executors/triple_barrier.py` (config only)
- Modify: `tests/unit/executors/test_triple_barrier.py`

- [ ] **Step 4.1: Write config tests**

```python
# tests/unit/executors/test_triple_barrier.py
from __future__ import annotations

from decimal import Decimal

import pytest
from strategy_framework.executors.triple_barrier import TripleBarrierExecutorConfig
from strategy_framework.executors.base import ExecutorConfigBase
from strategy_framework.primitives.enums import TradeType
from strategy_framework.primitives.triple_barrier import TripleBarrierConfig
from strategy_framework.primitives.trailing_stop import TrailingStop


def _tb_config(**kwargs: object) -> TripleBarrierExecutorConfig:
    defaults: dict[str, object] = dict(
        trading_pair="BTC-USDT",
        side=TradeType.BUY,
        entry_price=Decimal("50000"),
        amount=Decimal("0.01"),
        triple_barrier=TripleBarrierConfig(
            stop_loss=Decimal("0.02"),
            take_profit=Decimal("0.05"),
            time_limit_s=3600,
        ),
    )
    defaults.update(kwargs)
    return TripleBarrierExecutorConfig(**defaults)  # type: ignore[arg-type]


class TestTripleBarrierExecutorConfig:
    def test_is_executor_config_base(self) -> None:
        assert isinstance(_tb_config(), ExecutorConfigBase)

    def test_trailing_stop_defaults_to_none(self) -> None:
        assert _tb_config().trailing_stop is None

    def test_activation_bounds_defaults_to_none(self) -> None:
        assert _tb_config().activation_bounds is None

    def test_trailing_stop_can_be_set(self) -> None:
        ts = TrailingStop(activation_price_pct=Decimal("0.02"), trailing_delta_pct=Decimal("0.01"))
        config = _tb_config(trailing_stop=ts)
        assert config.trailing_stop == ts
```

- [ ] **Step 4.2: Run to verify failure**

```
pixi run pytest tests/unit/executors/test_triple_barrier.py::TestTripleBarrierExecutorConfig -v
```
Expected: `ImportError`

- [ ] **Step 4.3: Implement TripleBarrierExecutorConfig**

```python
# strategy_framework/executors/triple_barrier.py
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from strategy_framework.executors.base import ExecutorConfigBase
from strategy_framework.primitives.enums import TradeType
from strategy_framework.primitives.trailing_stop import TrailingStop
from strategy_framework.primitives.triple_barrier import TripleBarrierConfig


class TripleBarrierExecutorConfig(ExecutorConfigBase):
    trading_pair: str
    side: TradeType
    entry_price: Decimal
    amount: Decimal
    triple_barrier: TripleBarrierConfig           # uses time_limit_s field
    trailing_stop: Optional[TrailingStop] = None
    activation_bounds: Optional[tuple[Decimal, Decimal]] = None
```

- [ ] **Step 4.4: Run tests**

```
pixi run pytest tests/unit/executors/test_triple_barrier.py::TestTripleBarrierExecutorConfig -v
```
Expected: 4 PASSED

- [ ] **Step 4.5: Commit**

```
git add strategy_framework/executors/triple_barrier.py tests/unit/executors/test_triple_barrier.py
git commit -m "feat(executors): add TripleBarrierExecutorConfig"
```

---

## Task 5: TripleBarrierExecutor — Entry & Exit Logic

**Files:**
- Modify: `strategy_framework/executors/triple_barrier.py` — add TripleBarrierExecutor
- Modify: `tests/unit/executors/test_triple_barrier.py` — add executor tests

- [ ] **Step 5.1: Write failing tests for TripleBarrierExecutor**

Append to `tests/unit/executors/test_triple_barrier.py`:

```python
import datetime
from strategy_framework.executors.base import ExecutorState
from strategy_framework.executors.triple_barrier import TripleBarrierExecutor
from strategy_framework.primitives.enums import CloseType
from strategy_framework.testing.mock_market import MockMarketAccess


def make_tb_executor(
    entry_price: Decimal = Decimal("100"),
    amount: Decimal = Decimal("1"),
    stop_loss: Decimal = Decimal("0.02"),
    take_profit: Decimal = Decimal("0.05"),
    time_limit_s: int = 3600,
    trailing_stop: TrailingStop | None = None,
    activation_bounds: tuple[Decimal, Decimal] | None = None,
    mid_price: Decimal | None = None,
) -> tuple[TripleBarrierExecutor, MockMarketAccess]:
    market = MockMarketAccess()
    market.set_mid_price(mid_price if mid_price is not None else entry_price)
    config = TripleBarrierExecutorConfig(
        trading_pair="BTC-USDT",
        side=TradeType.BUY,
        entry_price=entry_price,
        amount=amount,
        triple_barrier=TripleBarrierConfig(
            stop_loss=stop_loss,
            take_profit=take_profit,
            time_limit_s=time_limit_s,
        ),
        trailing_stop=trailing_stop,
        activation_bounds=activation_bounds,
    )
    return TripleBarrierExecutor(market=market, config=config), market


class TestTripleBarrierExecutorEntry:
    def test_start_places_entry_order(self) -> None:
        ex, market = make_tb_executor()
        ex.start()
        assert len(market.order_history) == 1

    def test_start_within_activation_bounds_places_order(self) -> None:
        # bounds (0.99, 1.01): active when 49500 <= price <= 50500
        ex, market = make_tb_executor(
            entry_price=Decimal("50000"),
            activation_bounds=(Decimal("0.99"), Decimal("1.01")),
            mid_price=Decimal("50000"),
        )
        ex.start()
        assert ex.state == ExecutorState.ACTIVE
        assert len(market.order_history) == 1

    def test_start_outside_activation_bounds_stays_idle(self) -> None:
        ex, market = make_tb_executor(
            entry_price=Decimal("50000"),
            activation_bounds=(Decimal("0.99"), Decimal("1.01")),
            mid_price=Decimal("60000"),  # out of bounds
        )
        ex.start()
        assert ex.state == ExecutorState.IDLE
        assert len(market.order_history) == 0

    def test_price_update_while_idle_triggers_entry_when_in_bounds(self) -> None:
        ex, market = make_tb_executor(
            entry_price=Decimal("50000"),
            activation_bounds=(Decimal("0.99"), Decimal("1.01")),
            mid_price=Decimal("60000"),
        )
        ex.start()
        assert ex.state == ExecutorState.IDLE
        market.set_mid_price(Decimal("50000"))
        ex.notify_price_updated(Decimal("50000"))
        assert ex.state == ExecutorState.ACTIVE


class TestTripleBarrierExecutorExits:
    def test_take_profit_exit(self) -> None:
        ex, market = make_tb_executor(
            entry_price=Decimal("100"),
            take_profit=Decimal("0.05"),
        )
        ex.start()
        # First fill establishes entry — PNL mixin reads close_price == entry_price → 0%
        ex.notify_order_filled("o1", Decimal("100"), Decimal("1"))
        # Second fill at +6% — above TP 5%
        ex.notify_order_filled("o2", Decimal("106"), Decimal("1"))
        assert ex.state == ExecutorState.CLOSED

    def test_stop_loss_exit(self) -> None:
        ex, market = make_tb_executor(
            entry_price=Decimal("100"),
            stop_loss=Decimal("0.02"),
        )
        ex.start()
        ex.notify_order_filled("o1", Decimal("100"), Decimal("1"))
        # Fill at -3% — below SL 2%
        ex.notify_order_filled("o2", Decimal("97"), Decimal("1"))
        assert ex.state == ExecutorState.CLOSED

    def test_time_limit_exit(self) -> None:
        ex, market = make_tb_executor(time_limit_s=60)
        ex.start()
        ex.notify_order_filled("o1", Decimal("100"), Decimal("1"))
        now = datetime.datetime.now(datetime.timezone.utc)
        ex._started_at = now
        # Before limit — no exit
        ex.tick(now + datetime.timedelta(seconds=30))
        assert ex.state == ExecutorState.ACTIVE
        # After limit
        ex.tick(now + datetime.timedelta(seconds=61))
        assert ex.state == ExecutorState.CLOSED

    def test_trailing_stop_exit(self) -> None:
        # TrailingStop activates at +2% PnL, trigger = peak_pnl - 1%
        ts = TrailingStop(
            activation_price_pct=Decimal("0.02"),
            trailing_delta_pct=Decimal("0.01"),
        )
        ex, market = make_tb_executor(
            entry_price=Decimal("100"),
            trailing_stop=ts,
        )
        ex.start()
        ex.notify_order_filled("o1", Decimal("100"), Decimal("1"))
        ex.notify_price_updated(Decimal("103"))   # net_pnl_pct ≈ +3% → activates, sets trigger at +2%
        ex.notify_price_updated(Decimal("101.5")) # net_pnl_pct ≈ +1.5% < trigger +2% → fires
        assert ex.state == ExecutorState.CLOSED

    def test_entry_order_failure_closes_executor(self) -> None:
        ex, market = make_tb_executor()
        ex.start()
        ex.notify_order_failed("o1", "insufficient balance")
        assert ex.state == ExecutorState.CLOSED

    def test_partial_fill_does_not_trigger_exit_prematurely(self) -> None:
        ex, market = make_tb_executor(
            entry_price=Decimal("100"),
            take_profit=Decimal("0.05"),
        )
        ex.start()
        # Partial fill at entry — PnL is 0, no exit
        ex.notify_order_filled("o1", Decimal("100"), Decimal("0.5"))
        assert ex.state == ExecutorState.ACTIVE
        # Second partial fill still at entry price — still 0 PnL
        ex.notify_order_filled("o2", Decimal("100"), Decimal("0.5"))
        assert ex.state == ExecutorState.ACTIVE
```

- [ ] **Step 5.2: Run to verify failure**

```
pixi run pytest tests/unit/executors/test_triple_barrier.py -v -k "not Config"
```
Expected: `ImportError` or `AttributeError`

- [ ] **Step 5.3: Implement TripleBarrierExecutor**

Replace entire `strategy_framework/executors/triple_barrier.py` with:

```python
# strategy_framework/executors/triple_barrier.py
from __future__ import annotations

import datetime
import logging
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from strategy_framework.executors.base import ExecutorBase, ExecutorConfigBase, ExecutorState
from strategy_framework.executors.events import EventBus
from strategy_framework.mixins.executor.activation import ActivationBoundsMixin
from strategy_framework.mixins.executor.order_tracking import OrderTrackingMixin
from strategy_framework.mixins.executor.pnl import PNLCalculatorMixin
from strategy_framework.mixins.executor.trailing_stop import TrailingStopMixin
from strategy_framework.primitives.enums import CloseType, TradeType
from strategy_framework.primitives.trailing_stop import TrailingStop
from strategy_framework.primitives.triple_barrier import TripleBarrierConfig
from strategy_framework.testing.factories import TrackedOrderFactory

if TYPE_CHECKING:
    from strategy_framework.protocols.market import MarketAccessProtocol

logger = logging.getLogger(__name__)


class TripleBarrierExecutorConfig(ExecutorConfigBase):
    trading_pair: str
    side: TradeType
    entry_price: Decimal
    amount: Decimal
    triple_barrier: TripleBarrierConfig           # uses time_limit_s field
    trailing_stop: Optional[TrailingStop] = None
    activation_bounds: Optional[tuple[Decimal, Decimal]] = None


class TripleBarrierExecutor(
    ExecutorBase,
    ActivationBoundsMixin,
    OrderTrackingMixin,
    PNLCalculatorMixin,
    TrailingStopMixin,
):
    """Executor implementing triple-barrier exit logic.

    Host properties required by mixins:
    - ActivationBoundsMixin:  self.entry_price, self.activation_bounds
    - PNLCalculatorMixin:     self.entry_price, self.close_price,
                              self.open_filled_amount_quote, self.trade_side,
                              self.cum_fees_raw
    - TrailingStopMixin:      self.net_pnl_pct (provided by PNLCalculatorMixin)
    """

    def __init__(
        self,
        market: MarketAccessProtocol,
        config: TripleBarrierExecutorConfig,
        bus: Optional[EventBus] = None,
    ) -> None:
        ExecutorBase.__init__(self, market=market, config=config, bus=bus)
        self._init_order_tracking()
        self._init_trailing_stop(config.trailing_stop)
        self._started_at: Optional[datetime.datetime] = None
        # PNL host state — maintained as fills arrive
        self._close_price: Decimal = config.entry_price
        self._open_filled_amount_quote: Decimal = Decimal("0")
        self._cum_fees_raw: Decimal = Decimal("0")

    # ------------------------------------------------------------------ #
    # Mixin host properties — ActivationBoundsMixin                        #
    # ------------------------------------------------------------------ #

    @property
    def entry_price(self) -> Decimal:
        return self._config.entry_price  # type: ignore[return-value]

    @property
    def activation_bounds(self) -> Optional[tuple[Decimal, Decimal]]:
        return self._config.activation_bounds  # type: ignore[return-value]

    # ------------------------------------------------------------------ #
    # Mixin host properties — PNLCalculatorMixin                           #
    # ------------------------------------------------------------------ #

    @property
    def close_price(self) -> Decimal:
        return self._close_price

    @property
    def open_filled_amount_quote(self) -> Decimal:
        return self._open_filled_amount_quote

    @property
    def trade_side(self) -> TradeType:
        return self._config.side  # type: ignore[return-value]

    @property
    def cum_fees_raw(self) -> Decimal:
        return self._cum_fees_raw  # fees not tracked in Plan 3

    # ------------------------------------------------------------------ #
    # Lifecycle hooks                                                       #
    # ------------------------------------------------------------------ #

    def on_started(self) -> None:
        """Check activation bounds; place entry if within bounds, else stay IDLE."""
        mid = self._market.get_mid_price()
        if not self.is_within_activation_bounds(mid):
            # Bounds not met — revert to IDLE without placing order
            self._state = ExecutorState.IDLE
            return
        self._started_at = datetime.datetime.now(datetime.timezone.utc)
        self._place_entry_order()

    def on_price_updated(self, price: Decimal) -> None:
        if self.state == ExecutorState.IDLE:
            # Re-check activation bounds on each tick while waiting
            if self.is_within_activation_bounds(price):
                self._state = ExecutorState.ACTIVE
                self._started_at = datetime.datetime.now(datetime.timezone.utc)
                self._place_entry_order()
            return
        if self.state != ExecutorState.ACTIVE:
            return
        self._close_price = price
        if self._config.trailing_stop is not None:
            self.update_trailing_stop(price)
            if self.trailing_stop_triggered:
                self.stop(CloseType.TRAILING_STOP)
                return
        self.tick(datetime.datetime.now(datetime.timezone.utc))

    def on_order_filled(self, order_id: str, price: Decimal, amount: Decimal) -> None:
        # Track order via OrderTrackingMixin (requires TrackedOrderProtocol)
        filled = TrackedOrderFactory.filled_order(order_id=order_id, amount=amount, price=price)
        self.add_open_order(filled)
        # Update PNL host state
        self._close_price = price
        self._open_filled_amount_quote += amount * price
        self._check_barriers()

    def on_order_failed(self, order_id: str, reason: str) -> None:
        logger.warning("Order %s failed: %s", order_id, reason)
        self.stop(CloseType.FAILED)

    def on_stopped(self, close_type: CloseType) -> None:
        for order in list(self.open_orders):
            try:
                self._market.cancel_order(order.order_id)
            except Exception:
                logger.exception("Failed to cancel order %s on stop", order.order_id)

    # ------------------------------------------------------------------ #
    # Tick — time-limit check                                               #
    # ------------------------------------------------------------------ #

    def tick(self, now: datetime.datetime) -> None:
        if self.state != ExecutorState.ACTIVE or self._started_at is None:
            return
        tb = self._config.triple_barrier  # type: ignore[union-attr]
        if not tb.has_time_limit:
            return
        elapsed = (now - self._started_at).total_seconds()
        if elapsed >= tb.time_limit_s:
            self.stop(CloseType.TIME_LIMIT)

    # ------------------------------------------------------------------ #
    # Internal helpers                                                      #
    # ------------------------------------------------------------------ #

    def _place_entry_order(self) -> None:
        self._market.place_order(
            order_type="LIMIT",
            side=self._config.side.name,  # type: ignore[union-attr]
            amount=self._config.amount,  # type: ignore[union-attr]
            price=self._config.entry_price,  # type: ignore[union-attr]
        )

    def _check_barriers(self) -> None:
        pnl = self.trade_pnl_pct
        tb = self._config.triple_barrier  # type: ignore[union-attr]
        if tb.has_take_profit and pnl >= tb.take_profit:
            self.stop(CloseType.TAKE_PROFIT)
        elif tb.has_stop_loss and pnl <= -tb.stop_loss:
            self.stop(CloseType.STOP_LOSS)
```

- [ ] **Step 5.4: Verify mixin init requirements and CloseType members**

Before coding, confirm these facts from Plan 1/2 (they won't change, but be explicit):

- `ActivationBoundsMixin` — **no `_init_*()` call needed** (pure function, no state). Confirmed in `activation.py` docstring.
- `PNLCalculatorMixin` — **no `_init_*()` call needed** (all `@property`, no state). Confirmed in `pnl.py` docstring.
- `TrailingStopMixin` — **requires `self._init_trailing_stop(config.trailing_stop)`** (owns `_trailing_stop_config` and `_peak_pnl` state).
- `OrderTrackingMixin` — **requires `self._init_order_tracking()`** (owns `_open_orders`, `_close_orders` lists).
- `CloseType` members confirmed in `primitives/enums.py`: `STOP_LOSS`, `TAKE_PROFIT`, `TIME_LIMIT`, `TRAILING_STOP`, `FAILED`.

Add a comment in `TripleBarrierExecutor.__init__` documenting which mixins are init-free:

```python
# Mixin initialization:
# - OrderTrackingMixin: requires _init_order_tracking() — owns order lists
# - TrailingStopMixin: requires _init_trailing_stop() — owns peak_pnl state
# - ActivationBoundsMixin: init-free (pure function)
# - PNLCalculatorMixin: init-free (all @property, no internal state)
self._init_order_tracking()
self._init_trailing_stop(config.trailing_stop)
```

- [ ] **Step 5.6: Note on `TrackedOrderFactory` import in production code**

`TrackedOrderFactory` lives in `strategy_framework/testing/` — making `testing/` a runtime dependency in Plan 3. This is intentional and documented. Add a `# TODO(plan4): replace with primitives.TrackedOrder` comment on the import line. Plan 4 should introduce a proper `TrackedOrder` domain object in `strategy_framework/primitives/` to remove this dependency.

- [ ] **Step 5.5: Run tests**

```
pixi run pytest tests/unit/executors/test_triple_barrier.py -v
```
Expected: all PASSED (may need minor fixes to PNL mixin interface calls — align with Plan 2 mixin API)

- [ ] **Step 5.6: Run full suite**

```
pixi run test
```
Expected: all PASSED

- [ ] **Step 5.7: Commit**

```
git add strategy_framework/executors/triple_barrier.py tests/unit/executors/test_triple_barrier.py
git commit -m "feat(executors): implement TripleBarrierExecutor with TP/SL/time-limit/trailing-stop exits"
```

---

## Task 6: Integration Tests — Full Lifecycle

**Files:**
- Create (or modify): `tests/integration/test_executor_lifecycle.py`

- [ ] **Step 6.1: Write integration tests**

```python
# tests/integration/test_executor_lifecycle.py
from __future__ import annotations

import datetime
from decimal import Decimal

from strategy_framework.executors.base import ExecutorState
from strategy_framework.executors.triple_barrier import (
    TripleBarrierExecutor,
    TripleBarrierExecutorConfig,
)
from strategy_framework.primitives.enums import CloseType, TradeType
from strategy_framework.primitives.trailing_stop import TrailingStop
from strategy_framework.primitives.triple_barrier import TripleBarrierConfig
from strategy_framework.testing.mock_market import MockMarketAccess


def _make(
    entry_price: Decimal = Decimal("100"),
    stop_loss: Decimal = Decimal("0.02"),
    take_profit: Decimal = Decimal("0.05"),
    time_limit_s: int = 3600,
    trailing_stop: TrailingStop | None = None,
) -> tuple[TripleBarrierExecutor, MockMarketAccess]:
    market = MockMarketAccess()
    market.set_mid_price(entry_price)
    config = TripleBarrierExecutorConfig(
        trading_pair="BTC-USDT",
        side=TradeType.BUY,
        entry_price=entry_price,
        amount=Decimal("1"),
        triple_barrier=TripleBarrierConfig(
            stop_loss=stop_loss,
            take_profit=take_profit,
            time_limit_s=time_limit_s,
        ),
        trailing_stop=trailing_stop,
    )
    return TripleBarrierExecutor(market=market, config=config), market


class TestFullLifecycle:
    def test_happy_path_take_profit(self) -> None:
        ex, market = _make(entry_price=Decimal("100"), take_profit=Decimal("0.05"))
        assert ex.state == ExecutorState.IDLE
        ex.start()
        assert ex.state == ExecutorState.ACTIVE
        ex.notify_order_filled("o1", Decimal("100"), Decimal("1"))
        ex.notify_order_filled("o2", Decimal("106"), Decimal("1"))  # +6% > TP
        assert ex.state == ExecutorState.CLOSED

    def test_stop_loss_path(self) -> None:
        ex, market = _make(entry_price=Decimal("100"), stop_loss=Decimal("0.02"))
        ex.start()
        ex.notify_order_filled("o1", Decimal("100"), Decimal("1"))
        ex.notify_order_filled("o2", Decimal("97"), Decimal("1"))  # -3% < SL
        assert ex.state == ExecutorState.CLOSED

    def test_trailing_stop_path(self) -> None:
        ts = TrailingStop(
            activation_price_pct=Decimal("0.03"),
            trailing_delta_pct=Decimal("0.01"),
        )
        ex, market = _make(trailing_stop=ts)
        ex.start()
        ex.notify_order_filled("o1", Decimal("100"), Decimal("1"))
        ex.notify_price_updated(Decimal("104"))  # activates trailing stop
        ex.notify_price_updated(Decimal("102.5"))  # drops below trigger
        assert ex.state == ExecutorState.CLOSED

    def test_time_limit_path(self) -> None:
        ex, market = _make(time_limit_s=60)
        ex.start()
        ex.notify_order_filled("o1", Decimal("100"), Decimal("1"))
        assert ex.state == ExecutorState.ACTIVE
        t0 = datetime.datetime.now(datetime.timezone.utc)
        ex._started_at = t0
        ex.tick(t0 + datetime.timedelta(seconds=61))
        assert ex.state == ExecutorState.CLOSED

    def test_state_at_each_step(self) -> None:
        ex, _ = _make()
        assert ex.state == ExecutorState.IDLE
        ex.start()
        assert ex.state == ExecutorState.ACTIVE
        ex.notify_order_filled("o1", Decimal("100"), Decimal("1"))
        assert ex.state == ExecutorState.ACTIVE
        ex.notify_order_filled("o2", Decimal("106"), Decimal("1"))
        assert ex.state == ExecutorState.CLOSED
```

- [ ] **Step 6.2: Run integration tests**

```
pixi run pytest tests/integration/test_executor_lifecycle.py -v
```
Expected: 5 PASSED

- [ ] **Step 6.3: Run full suite**

```
pixi run test
```
Expected: all PASSED (~200 total)

- [ ] **Step 6.4: Commit**

```
git add tests/integration/test_executor_lifecycle.py
git commit -m "test(executors): add full lifecycle integration tests for TripleBarrierExecutor"
```

---

## Task 7: Public API + Exports

**Files:**
- Modify: `strategy_framework/executors/__init__.py`
- Modify: `strategy_framework/__init__.py`

- [ ] **Step 7.1: Update executors __init__.py**

```python
# strategy_framework/executors/__init__.py
"""Executor layer — ExecutorBase and concrete executor implementations."""

from strategy_framework.executors.base import (
    ExecutorBase,
    ExecutorConfigBase,
    ExecutorState,
    ExecutorStateError,
)
from strategy_framework.executors.triple_barrier import (
    TripleBarrierExecutor,
    TripleBarrierExecutorConfig,
)

__all__ = [
    "ExecutorBase",
    "ExecutorConfigBase",
    "ExecutorState",
    "ExecutorStateError",
    "TripleBarrierExecutor",
    "TripleBarrierExecutorConfig",
]
```

- [ ] **Step 7.2: Add executor exports to top-level __init__.py**

In `strategy_framework/__init__.py`, add after existing imports:

```python
from strategy_framework.executors import (
    ExecutorBase,
    ExecutorConfigBase,
    ExecutorState,
    ExecutorStateError,
    TripleBarrierExecutor,
    TripleBarrierExecutorConfig,
)
```

And add to `__all__`:
```python
"ExecutorBase",
"ExecutorConfigBase",
"ExecutorState",
"ExecutorStateError",
"TripleBarrierExecutor",
"TripleBarrierExecutorConfig",
```

- [ ] **Step 7.3: Run full suite + typecheck + lint**

```
pixi run test
pixi run typecheck
pixi run lint
```
Expected: all PASSED, no violations

- [ ] **Step 7.4: Final commit**

```
git add strategy_framework/executors/__init__.py strategy_framework/__init__.py
git commit -m "feat(executors): expose executor layer in public API"
```

---

## Coverage Check

```
pixi run test --cov=strategy_framework/executors --cov-report=term-missing
```

Target: ≥90% for `executors/` module.
