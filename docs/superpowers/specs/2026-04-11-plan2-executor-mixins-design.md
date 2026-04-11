# Plan 2: Executor Mixin Layer

**Date:** 2026-04-11
**Status:** Approved
**Repo:** MementoRC/hb-strategy-framework
**Builds on:** Plan 1 Foundation (protocols, primitives, testing infrastructure)

---

## Goal

Create a clean, protocol-typed executor mixin layer in `strategy_framework/mixins/executor/`. Seven mixins port proven algorithms from the hummingbot in-tree executor mixins while replacing all hummingbot-internal type dependencies with strategy-framework protocol composites.

**Out of scope:** Full executor implementations, market adapter, live-market sub-package integration.

---

## Approach: Hybrid (Port + Protocol Redesign)

Port proven algorithms verbatim (trailing stop ratchet, PNL formula, retry counter). Redesign the public API using Plan 1 protocol composites as `self:` types. No hummingbot imports anywhere in the mixin layer.

---

## Module Structure

```
strategy_framework/
├── mixins/
│   ├── __init__.py
│   └── executor/
│       ├── __init__.py
│       ├── retry.py           # RetryMixin
│       ├── shutdown.py        # ShutdownMixin
│       ├── activation.py      # ActivationBoundsMixin
│       ├── balance.py         # BalanceValidationMixin (stub)
│       ├── order_tracking.py  # OrderTrackingMixin
│       ├── pnl.py             # PNLCalculatorMixin
│       └── trailing_stop.py   # TrailingStopMixin

tests/unit/mixins/executor/
├── test_retry.py
├── test_shutdown.py
├── test_activation.py
├── test_balance.py
├── test_order_tracking.py
├── test_pnl.py
└── test_trailing_stop.py

tests/integration/
└── test_mixin_composition.py   # MRO safety, attribute collision checks
```

---

## Protocol Changes (modifications to Plan 1 files)

### 1. `protocols/market.py` — extend `MarketAccessProtocol`

Add one method to the existing protocol:

```python
def get_available_balance(self, currency: str) -> Decimal: ...
```

**Why:** `BalanceValidationMixin` stubs against this. Future live-market sub-package and market-simulator adapter will implement it. Mirrors `BalanceProtocol.get_available_balance` from hb-market-simulator.

### 2. `protocols/composites.py` — add `ActivationBoundsProtocol`

```python
class ActivationBoundsProtocol(Protocol):
    entry_price: Decimal
    activation_bounds: tuple[Decimal, Decimal] | None
```

**Why:** `ActivationBoundsMixin` needs to read `entry_price` and `activation_bounds` from the host class. Kept separate from existing composites — narrow contract.

### 3. `testing/factories.py` — add `TrackedOrderFactory`

```python
class TrackedOrderFactory:
    @staticmethod
    def open_order(
        order_id: str = "mock_0001",
        amount: Decimal = Decimal("1.0"),
        price: Decimal = Decimal("100.0"),
        side: str = "BUY",
    ) -> TrackedOrderProtocol: ...

    @staticmethod
    def filled_order(
        order_id: str = "mock_0001",
        amount: Decimal = Decimal("1.0"),
        price: Decimal = Decimal("100.0"),
    ) -> TrackedOrderProtocol: ...
```

**Why:** `OrderTrackingMixin` tests need concrete `TrackedOrderProtocol` instances without depending on hummingbot's `InFlightOrder`.

---

## Mixin Designs

All stateful mixins initialize via `_init_<mixin>()`. Callers must invoke these in `__init__` after `super().__init__()`. MRO-safe call order documented in each mixin's docstring.

### RetryMixin — `self: RetryProtocol`

```python
# State (init via _init_retry())
current_retries: int = 0

# API
def _init_retry(self: RetryProtocol) -> None
def increment_retries(self: RetryProtocol) -> None
def has_exceeded_max_retries(self: RetryProtocol) -> bool
```

Host must provide: `max_retries: int`.

### ShutdownMixin — `self: ShutdownProtocol`

```python
# API
def shutdown(self: ShutdownProtocol) -> None
@property
def has_pending_orders(self: ShutdownProtocol) -> bool
```

Initiates graceful shutdown; polls `has_pending_orders` until flat. Host must provide: mechanism to enumerate pending orders.

### ActivationBoundsMixin — `self: ActivationBoundsProtocol`

```python
# API — pure function, no market dependency
def is_within_activation_bounds(
    self: ActivationBoundsProtocol, current_price: Decimal
) -> bool
```

Caller provides `current_price`. Returns `True` if `activation_bounds is None` (always active). Host must provide: `entry_price: Decimal`, `activation_bounds: tuple[Decimal, Decimal] | None`.

### BalanceValidationMixin — `self: MarketAccessProtocol` (extended)

```python
# STUB
def validate_balance(
    self: MarketAccessProtocol, currency: str, amount: Decimal
) -> bool:
    # TODO: requires a market adapter implementing get_available_balance().
    # Implement when hb-market-simulator adapter or live-market sub-package exists.
    raise NotImplementedError(
        "BalanceValidationMixin.validate_balance requires a concrete market "
        "adapter that implements MarketAccessProtocol.get_available_balance(). "
        "See hb-market-simulator BalanceProtocol for the expected interface."
    )
```

Tests verify only that the stub raises `NotImplementedError` with the correct message.

### OrderTrackingMixin — `self: OrderTrackingProtocol`

```python
# State (init via _init_order_tracking())
open_orders: list[TrackedOrderProtocol] = []
close_orders: list[TrackedOrderProtocol] = []

# API
def _init_order_tracking(self: OrderTrackingProtocol) -> None
def add_open_order(self: OrderTrackingProtocol, order: TrackedOrderProtocol) -> None
def add_close_order(self: OrderTrackingProtocol, order: TrackedOrderProtocol) -> None
def update_tracked_order(self: OrderTrackingProtocol, order_id: str, **kwargs) -> None
def get_filled_open_orders(self: OrderTrackingProtocol) -> list[TrackedOrderProtocol]
def get_open_order(self: OrderTrackingProtocol, order_id: str) -> TrackedOrderProtocol | None
```

Decoupled from `InFlightOrder` — works with any `TrackedOrderProtocol` implementation.

### PNLCalculatorMixin — `self: PnLProtocol`

```python
# Pure computed properties — no state, no _init_ required
@property
def trade_pnl_pct(self: PnLProtocol) -> Decimal
@property
def trade_pnl_quote(self: PnLProtocol) -> Decimal
@property
def cum_fees_quote(self: PnLProtocol) -> Decimal
@property
def net_pnl_pct(self: PnLProtocol) -> Decimal      # trade_pnl_pct - fees_pct
@property
def net_pnl_quote(self: PnLProtocol) -> Decimal     # trade_pnl_quote - cum_fees_quote
```

Formula ported verbatim from hummingbot: `net_pnl = trade_pnl - fees`. Host must provide: filled amounts, entry/exit prices, fee data.

### TrailingStopMixin — `self: BarrierControlProtocol`

```python
# State (init via _init_trailing_stop())
_trailing_stop_price: Decimal | None = None
_trailing_stop_activated: bool = False

# API
def _init_trailing_stop(self: BarrierControlProtocol) -> None
def update_trailing_stop(
    self: BarrierControlProtocol, current_price: Decimal
) -> None  # SIDE EFFECT: advances trailing stop price floor (ratchet)
@property
def trailing_stop_triggered(self: BarrierControlProtocol) -> bool
@property
def trailing_stop_activated(self: BarrierControlProtocol) -> bool
```

Ratchet algorithm ported verbatim from hummingbot. Side-effect of `update_trailing_stop` is intentional and documented — it advances the price floor; do not call speculatively. Host must provide: `TrailingStop` config from primitives.

---

## Testing Strategy

**Unit tests (~75-85 total):** One file per mixin, ~10-12 tests each.

Pattern — minimal concrete class implementing only the required composite protocol:

```python
class ConcreteRetry(RetryMixin):
    current_retries: int = 0
    max_retries: int = 3

def test_increment_retries_advances_counter() -> None:
    obj = ConcreteRetry()
    obj._init_retry()
    obj.increment_retries()
    assert obj.current_retries == 1

def test_has_exceeded_max_retries_true_at_limit() -> None:
    obj = ConcreteRetry()
    obj._init_retry()
    for _ in range(3):
        obj.increment_retries()
    assert obj.has_exceeded_max_retries() is True
```

**Integration test (`tests/integration/test_mixin_composition.py`):**

Verifies MRO-safe `_init_*()` call order and no attribute collisions when composing multiple mixins:

```python
class CompositeExecutor(RetryMixin, TrailingStopMixin, OrderTrackingMixin):
    # implements RetryProtocol + BarrierControlProtocol + OrderTrackingProtocol
    ...

def test_composite_executor_initializes_all_mixin_state() -> None: ...
def test_trailing_stop_and_retry_state_independent() -> None: ...
def test_order_tracking_unaffected_by_retry_increment() -> None: ...
```

**Quality gates:** ≥90% coverage, mypy strict, ruff clean — matching Plan 1.

---

## What This Enables for Plan 3

Controller building blocks can import `TrailingStopMixin`, `PNLCalculatorMixin`, `OrderTrackingMixin` directly. Composition without re-implementing the math. The `BalanceValidationMixin` stub interface is established so Plan 3 controller mixins can reference it by contract.

---

## Source References

- Existing mixins to port from: `hummingbot/strategy_v2/executors/mixins/`
- Plan 1 composites: `strategy_framework/protocols/composites.py`
- Plan 1 primitives (TrailingStop, TripleBarrierConfig): `strategy_framework/primitives/`
- market-simulator BalanceProtocol: `sub-packages/market-simulator/market_simulator/protocols/connector.py`
