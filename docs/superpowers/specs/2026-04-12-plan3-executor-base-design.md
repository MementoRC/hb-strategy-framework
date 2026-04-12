# Plan 3: ExecutorBase & TripleBarrierExecutor — Design Spec

**Date:** 2026-04-12
**Status:** Approved
**Builds on:** Plan 1 (Foundation), Plan 2 (Executor Mixin Layer)
**Next:** Plan 4 (Controller Layer)

---

## Goal

Add `strategy_framework/executors/` — a concrete `ExecutorBase` with an event-driven lifecycle and a `TripleBarrierExecutor` that assembles four Plan 2 mixins. This is the first complete, runnable trading unit in the framework, and the bridge toward replacing `strategy_v2` live logic with a market_simulator-compatible interface.

---

## Context & Motivation

The existing hummingbot `strategy_v2` framework uses a tick-driven lifecycle inherited from `pure_market_making`-era designs. This plan introduces an event-driven alternative that:

- Matches `hb-market-simulator`'s DI-first, protocol-typed interface
- Eliminates hummingbot-internal dependencies from executor logic
- Composes behavior from Plan 2 mixins rather than duplicating algorithms
- Provides a clean path to re-architecting live trading logic with a sim-compatible interface

---

## Architecture

### Approach

**Approach A — ExecutorBase + TripleBarrierExecutor (focused)**

`ExecutorBase` with a validated state machine, 6 dedicated event hooks (guaranteed delivery), and a lightweight internal `EventBus` for secondary handlers. `TripleBarrierExecutor` assembles `ActivationBoundsMixin`, `OrderTrackingMixin`, `PNLCalculatorMixin`, and `TrailingStopMixin` via MRO composition.

The `EventBus` is internal to the executors module for now, but designed to be extractable to `strategy_framework/events/` when the Controller layer (Plan 4) needs shared pub/sub.

---

## File Structure

```
strategy_framework/
├── executors/
│   ├── __init__.py           # Re-exports: ExecutorBase, TripleBarrierExecutor, ExecutorState, ExecutorStateError
│   ├── base.py               # ExecutorBase — state machine + hooks + bus wiring
│   ├── events.py             # EventBus + typed event dataclasses (internal)
│   └── triple_barrier.py     # TripleBarrierExecutor + TripleBarrierConfig
tests/
├── unit/
│   └── executors/
│       ├── __init__.py
│       ├── test_base.py          # State machine, hook dispatch, bus subscription
│       ├── test_events.py        # EventBus subscribe/emit/unsubscribe
│       └── test_triple_barrier.py
└── integration/
    └── test_executor_lifecycle.py  # Full lifecycle with MockMarketAccess
```

Modify: `strategy_framework/__init__.py` — add executor exports.

---

## ExecutorBase

### Constructor

```python
ExecutorBase(market: MarketAccessProtocol, config: StrategyConfigBase)
```

Matches market_simulator's DI pattern. `market` is the sole interface for all exchange operations.

### State Machine

```
IDLE → ACTIVE → CLOSING → CLOSED
```

`ExecutorState` is an enum. Transitions are validated — invalid transitions raise `ExecutorStateError`. State is read-only externally.

| State | Meaning |
|-------|---------|
| `IDLE` | Created, not yet started |
| `ACTIVE` | Entry placed or filled, managing position |
| `CLOSING` | Exit triggered, awaiting order confirmation |
| `CLOSED` | Terminal — position closed, no further transitions |

### Dedicated Event Hooks

Called **before** the EventBus fires — guaranteed first-class delivery regardless of bus load.

```python
def on_started(self) -> None: ...
def on_stopped(self, close_type: CloseType) -> None: ...
def on_order_filled(self, order_id: str, price: Decimal, amount: Decimal) -> None: ...
def on_order_cancelled(self, order_id: str) -> None: ...
def on_order_failed(self, order_id: str, reason: str) -> None: ...
def on_price_updated(self, price: Decimal) -> None: ...
```

Subclasses override these. Default implementations are no-ops (not abstract) so `ExecutorBase` can be instantiated directly in tests.

### EventBus Integration

Each executor owns one `EventBus` instance (injected at construction or created internally). After dedicated hooks fire, the same event is emitted on the bus for secondary handlers.

```python
executor.bus.subscribe("order.filled", my_handler)
executor.bus.unsubscribe("order.filled", my_handler)
```

---

## EventBus (`events.py`)

Lightweight pub/sub. Not a dependency of any other module yet.

**Typed event dataclasses:**

```python
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
```

**API:**

```python
bus.subscribe(event_type: str, handler: Callable[[Any], None]) -> None
bus.emit(event_type: str, event: Any) -> None
bus.unsubscribe(event_type: str, handler: Callable[[Any], None]) -> None
```

Handlers are called synchronously in subscription order. Exceptions in handlers are caught and logged — they do not interrupt other handlers.

---

## TripleBarrierExecutor

### Inheritance

```python
class TripleBarrierExecutor(
    ExecutorBase,
    ActivationBoundsMixin,
    OrderTrackingMixin,
    PNLCalculatorMixin,
    TrailingStopMixin,
):
```

`TrailingStopMixin` is composed unconditionally; trailing stop logic activates only when `config.trailing_stop is not None`.

### Config

```python
class TripleBarrierExecutorConfig(StrategyConfigBase):
    trading_pair: str
    side: TradeType
    entry_price: Decimal
    amount: Decimal
    triple_barrier: TripleBarrierConfig      # stop_loss, take_profit, time_limit (Plan 1)
    trailing_stop: TrailingStop | None = None
    activation_bounds: tuple[Decimal, Decimal] | None = None
```

### Hook Wiring

| Hook | Action |
|------|--------|
| `on_started` | Validate activation bounds; if within bounds (or no bounds), place entry order via `market.place_order(...)` |
| `on_order_filled` | Track order via `OrderTrackingMixin`; update PnL via `PNLCalculatorMixin`; check TP/SL exits |
| `on_price_updated` | Re-check activation bounds; update trailing stop ratchet; check time limit |
| `on_order_cancelled` | Log; re-evaluate state (may re-enter or close) |
| `on_order_failed` | Transition to CLOSING; emit `CloseType.FAILED` |
| `on_stopped` | Cancel all open orders via `market.cancel_order(...)`; emit final PnL via bus |

### Exit Triggers

Checked in `on_order_filled` and `on_price_updated`:

| Trigger | Condition |
|---------|-----------|
| Take profit | `pnl_pct >= triple_barrier.take_profit` |
| Stop loss | `pnl_pct <= -triple_barrier.stop_loss` |
| Time limit | `elapsed_seconds >= triple_barrier.time_limit` |
| Trailing stop | `TrailingStopMixin.trailing_stop_triggered` |

All exits transition to `CLOSING` and call `stop(close_type)` which fires `on_stopped`.

---

## Testing Strategy

**Target:** ≥90% coverage (consistent with Plans 1 & 2). No new test infrastructure — `MockMarketAccess`, `ExecutorTestHarness`, `TrackedOrderFactory` from Plans 1-2 are sufficient.

### Unit Tests

| File | Covers |
|------|--------|
| `test_base.py` | Valid/invalid state transitions, `ExecutorStateError`, hook dispatch order (hooks before bus), bus wiring |
| `test_events.py` | Subscribe, emit, unsubscribe, multiple handlers, handler exception isolation |
| `test_triple_barrier.py` | TP exit, SL exit, time limit exit, trailing stop exit, activation bounds gate, partial fills, entry order failure |

### Integration Tests (`test_executor_lifecycle.py`)

Full lifecycle via `MockMarketAccess`:

- Entry → fill → TP close (happy path)
- Entry → price move → SL close
- Entry → trailing stop activation → ratchet → trigger
- Entry → time limit expire
- State verified at each step via `executor.state`

### Estimated Test Count

~45–55 new tests. Total suite: ~200 tests.

---

## Protocol Amendments

None required — all needed protocols (`MarketAccessProtocol`, `ExecutorProtocol`, composite protocols) were established in Plans 1 and 2.

---

## Public API Additions

`strategy_framework/__init__.py` gains:

```python
from strategy_framework.executors import (
    ExecutorBase,
    ExecutorState,
    ExecutorStateError,
    TripleBarrierExecutor,
    TripleBarrierExecutorConfig,
)
```

---

## Out of Scope (Plan 4+)

- Controller layer (orchestrates multiple executors)
- Extracting `EventBus` to `strategy_framework/events/` (done when Controller needs it)
- Additional concrete executors (GridExecutor, DCAExecutor, etc.)
- Live market adapter (bridges `MarketAccessProtocol` to hummingbot exchange connectors)
