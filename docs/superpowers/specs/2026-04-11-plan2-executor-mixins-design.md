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

Port proven algorithms verbatim where possible (trailing stop ratchet, PNL formula, retry counter). Redesign the public API and type contracts using Plan 1 protocol composites as `self:` host types. No hummingbot imports anywhere in the mixin layer.

Three mixins are **deliberate redesigns**, not ports — see individual sections for rationale.

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
│       ├── activation.py      # ActivationBoundsMixin  [redesign]
│       ├── balance.py         # BalanceValidationMixin (stub)
│       ├── order_tracking.py  # OrderTrackingMixin     [redesign]
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
└── test_mixin_composition.py
```

---

## Protocol Changes (modifications to Plan 1 files)

All changes are additive or non-breaking amendments to `strategy_framework/protocols/`.

### 1. `protocols/market.py` — extend `MarketAccessProtocol`

Add one method:

```python
def get_available_balance(self, currency: str) -> Decimal: ...
```

`BalanceValidationMixin` stubs against this. Future live-market sub-package and market-simulator adapter will implement it. Mirrors `BalanceProtocol.get_available_balance` from hb-market-simulator.

### 2. `protocols/composites.py` — seven amendments

**2a. Add `RetryHostProtocol`** (new — host contract for `RetryMixin`):

```python
class RetryHostProtocol(Protocol):
    """What the host must provide for RetryMixin to operate."""
    max_retries: int
```

`RetryMixin` types `self:` against `RetryHostProtocol` — not against `RetryProtocol`. `RetryProtocol` is the *consumer-facing output contract* (what callers observe on a class that has `RetryMixin`). Mixing the two caused a circular self-reference in the original spec draft.

**2b. Amend `RetryProtocol`** — replace the existing `@property current_retries` declaration (composites.py lines 62-63) with a plain attribute:

```python
# BEFORE (lines 62-63 in composites.py):
#     @property
#     def current_retries(self) -> int: ...

# AFTER:
class RetryProtocol(Protocol):
    current_retries: int      # plain attribute, not @property
    max_retries: int
    def increment_retries(self) -> None: ...
```

This is a replacement, not an addition — do not leave the `@property` form alongside the new declaration. `RetryMixin` will store `current_retries` as a plain `int` instance attribute (initialized in `_init_retry()`). A `@property` declaration in the protocol would require a matching property in every concrete class; a plain attribute is simpler and `mypy --strict` accepts a plain attribute satisfying either form.

**2c. Add `PnLHostProtocol`** (new — host contract for `PNLCalculatorMixin`):

```python
class PnLHostProtocol(Protocol):
    """What the host must provide for PNLCalculatorMixin to compute PnL."""

    @property
    def entry_price(self) -> Decimal: ...

    @property
    def close_price(self) -> Decimal: ...

    @property
    def open_filled_amount_quote(self) -> Decimal: ...

    @property
    def trade_side(self) -> TradeType: ...

    @property
    def cum_fees_raw(self) -> Decimal: ...
```

`PNLCalculatorMixin` types `self:` against `PnLHostProtocol`. The existing `PnLProtocol` remains the *output contract* — what consumers see on a class that has `PNLCalculatorMixin`.

**2d. Add `trade_pnl_quote` to `PnLProtocol`**:

```python
@runtime_checkable
class PnLProtocol(Protocol):
    @property
    def net_pnl_pct(self) -> Decimal: ...
    @property
    def net_pnl_quote(self) -> Decimal: ...
    @property
    def cum_fees_quote(self) -> Decimal: ...
    @property
    def trade_pnl_pct(self) -> Decimal: ...
    @property
    def trade_pnl_quote(self) -> Decimal: ...  # ADD THIS
```

**2e. Add `ActivationBoundsProtocol`** (new — host contract for `ActivationBoundsMixin`):

```python
class ActivationBoundsProtocol(Protocol):
    """What the host must provide for ActivationBoundsMixin."""
    entry_price: Decimal
    activation_bounds: tuple[Decimal, Decimal] | None
```

Bounds semantics: `(lower_multiplier, upper_multiplier)` relative to `entry_price`. Example: `(Decimal("0.99"), Decimal("1.01"))` means active when `entry_price * 0.99 <= current_price <= entry_price * 1.01`. `None` means always active.

**2f. Amend `OrderTrackingProtocol`** — update `update_tracked_order` signature:

```python
class OrderTrackingProtocol(Protocol):
    @property
    def open_orders(self) -> list[object]: ...
    @property
    def close_orders(self) -> list[object]: ...
    def update_tracked_order(self, order_id: str, **kwargs: object) -> None: ...  # AMENDED
```

The original two-parameter signature `(order_id, exchange_order_id)` was hummingbot-specific. The `**kwargs` form is more general and allows enriching order state without tying the protocol to exchange internals.

**2g. Amend `BarrierControlProtocol`** — verify `trailing_stop` field uses `TrailingStop` primitive:

No change needed — `trailing_stop: TrailingStop | None` is already correct in Plan 1. Document for implementers: the ratchet algorithm reads `trailing_stop.activation_price_pct` and `trailing_stop.trailing_delta_pct` (with `_pct` suffix, per `strategy_framework/primitives/trailing_stop.py`).

### 3. `testing/factories.py` — add `TrackedOrderFactory`

```python
class TrackedOrderFactory:
    @staticmethod
    def open_order(
        order_id: str = "mock_0001",
        amount: Decimal = Decimal("1.0"),
        price: Decimal = Decimal("100.0"),
        side: str = "BUY",
    ) -> TrackedOrderProtocol:
        """Returns a mock open (unfilled) order."""

    @staticmethod
    def filled_order(
        order_id: str = "mock_0001",
        amount: Decimal = Decimal("1.0"),
        price: Decimal = Decimal("100.0"),
    ) -> TrackedOrderProtocol:
        """Returns a mock fully-filled order.
        filled_amount = amount, is_filled = True, is_open = False.
        """
```

The mock satisfies all five `TrackedOrderProtocol` fields: `order_id`, `is_filled`, `is_open`, `filled_amount`, `average_price`.

---

## Mixin Designs

**MRO init pattern:** All stateful mixins initialize via `_init_<mixin>()`. Callers invoke these in `__init__` after `super().__init__()`. Calling `_init_<mixin>()` twice resets state to initial values (safe in diamond MRO scenarios). Each mixin's docstring lists its required call order relative to other mixins.

---

### RetryMixin — `self: RetryHostProtocol`

**Port.** Logic verbatim from `hummingbot/strategy_v2/executors/mixins/retry.py`.

```python
# State (init via _init_retry())
current_retries: int = 0  # plain int attribute

# API
def _init_retry(self: RetryHostProtocol) -> None
def increment_retries(self: RetryHostProtocol) -> None
def has_exceeded_max_retries(self: RetryHostProtocol) -> bool
    # Returns True when current_retries >= max_retries
    # NOTE: uses >= (not >) — triggers at exactly max_retries, not one beyond
```

Host must provide: `max_retries: int`.

**Boundary note:** The in-tree version uses `current_retries > max_retries` (triggers at `max_retries + 1`). This mixin deliberately switches to `>=` (triggers at exactly `max_retries`) for clearer semantics. Tests assert `has_exceeded_max_retries()` is `True` after exactly `max_retries` calls to `increment_retries()`.

---

### ShutdownMixin — `self: ShutdownProtocol`

**Synchronous redesign.** The in-tree version has an async poll loop (`control_shutdown_process`). This mixin provides only the *state management* half — shutdown flag + pending orders check. The async loop is the host executor's responsibility.

```python
# State (init via _init_shutdown())
_shutdown_requested: bool = False

# API
def _init_shutdown(self: ShutdownProtocol) -> None
def request_shutdown(self: ShutdownProtocol) -> None   # sets _shutdown_requested = True
@property
def shutdown_requested(self: ShutdownProtocol) -> bool
@property
def has_pending_orders(self: ShutdownProtocol) -> bool  # abstract — host implements
```

`has_pending_orders` is declared in the mixin as `raise NotImplementedError` — the host executor overrides it to inspect its own order state. The mixin provides `shutdown_requested` flag; the host's async loop checks both.

Host must provide: override of `has_pending_orders`.

---

### ActivationBoundsMixin — `self: ActivationBoundsProtocol`

**Deliberate redesign.** The in-tree version takes `(order_price, side, order_type)` and calls `self.get_price(connector, pair, PriceType.MidPrice)` internally, performing four check variants (limit/market × buy/sell). This version removes the market-access dependency and collapses to a single bounds check:

```python
# No state, no _init_ required

# API — pure function, current_price provided by caller
def is_within_activation_bounds(
    self: ActivationBoundsProtocol, current_price: Decimal
) -> bool
    # Returns True if activation_bounds is None (always active)
    # Otherwise: entry_price * bounds[0] <= current_price <= entry_price * bounds[1]
```

**Rationale:** Removing side/order-type variants eliminates the market-access call inside the mixin, making it testable without any mock exchange. The side asymmetry (buy checks lower, sell checks upper) is dropped — callers that need asymmetric bounds can subclass and override.

Host must provide: `entry_price: Decimal`, `activation_bounds: tuple[Decimal, Decimal] | None`.

---

### BalanceValidationMixin — `self: MarketAccessProtocol` (extended)

**Stub only.**

```python
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

Tests verify only that the stub raises `NotImplementedError` with this exact message.

---

### OrderTrackingMixin — `self: OrderTrackingProtocol`

**Deliberate redesign.** The in-tree version is a narrow mixin focused solely on matching an order ID to an exchange order ID. This version lifts the full order list management into the mixin — a broader but more cohesive interface.

```python
# State (init via _init_order_tracking())
open_orders: list[TrackedOrderProtocol] = []
close_orders: list[TrackedOrderProtocol] = []

# API
def _init_order_tracking(self: OrderTrackingProtocol) -> None
def add_open_order(self: OrderTrackingProtocol, order: TrackedOrderProtocol) -> None
def add_close_order(self: OrderTrackingProtocol, order: TrackedOrderProtocol) -> None
def update_tracked_order(
    self: OrderTrackingProtocol, order_id: str, **kwargs: object
) -> None
def get_filled_open_orders(self: OrderTrackingProtocol) -> list[TrackedOrderProtocol]
def get_open_order(
    self: OrderTrackingProtocol, order_id: str
) -> TrackedOrderProtocol | None
```

Decoupled from `InFlightOrder` — works with any `TrackedOrderProtocol` implementation.

---

### PNLCalculatorMixin — `self: PnLHostProtocol`

**Port with host-protocol substitution.** The in-tree version uses five abstract template methods (`_get_entry_price`, `_get_close_price`, etc.). This version replaces those with `PnLHostProtocol` — the host declares the required properties; the mixin reads them.

```python
# No state, no _init_ required — pure computed properties

@property
def trade_pnl_pct(self: PnLHostProtocol) -> Decimal
@property
def trade_pnl_quote(self: PnLHostProtocol) -> Decimal
@property
def cum_fees_quote(self: PnLHostProtocol) -> Decimal
@property
def net_pnl_pct(self: PnLHostProtocol) -> Decimal      # trade_pnl_pct - fees_pct
@property
def net_pnl_quote(self: PnLHostProtocol) -> Decimal     # trade_pnl_quote - cum_fees_quote
```

Formula ported verbatim: `net_pnl = trade_pnl - fees`.

Host must provide (via `PnLHostProtocol`): `entry_price`, `close_price`, `open_filled_amount_quote`, `trade_side`, `cum_fees_raw`.

---

### TrailingStopMixin — `self: BarrierControlProtocol`

**Port.** Ratchet algorithm ported verbatim from hummingbot. `BarrierControlProtocol` already exposes `trailing_stop: TrailingStop | None` — no new composite needed.

```python
# State (init via _init_trailing_stop())
_trailing_stop_price: Decimal | None = None
_trailing_stop_activated: bool = False

# API
def _init_trailing_stop(self: BarrierControlProtocol) -> None
def update_trailing_stop(
    self: BarrierControlProtocol, current_price: Decimal
) -> None
# SIDE EFFECT: may advance the trailing stop price floor (ratchet).
# Do not call speculatively — call only once per price tick.
@property
def trailing_stop_triggered(self: BarrierControlProtocol) -> bool
@property
def trailing_stop_activated(self: BarrierControlProtocol) -> bool
```

**Field names for implementers:** the ratchet algorithm reads `trailing_stop.activation_price_pct` and `trailing_stop.trailing_delta_pct` (note the `_pct` suffix — defined in `strategy_framework/primitives/trailing_stop.py`). Do **not** use the in-tree names `activation_price` / `trailing_delta` (no suffix) — those will NameError.

---

## Testing Strategy

**Unit tests (~75-85 total):** One file per mixin, ~10-12 tests each.

Pattern — minimal concrete class implementing only the required host protocol:

```python
class ConcreteRetry(RetryMixin):
    max_retries: int = 3

    def __init__(self) -> None:
        self._init_retry()

def test_increment_retries_advances_counter() -> None:
    obj = ConcreteRetry()
    obj.increment_retries()
    assert obj.current_retries == 1

def test_has_exceeded_at_exactly_max_retries() -> None:
    obj = ConcreteRetry()
    for _ in range(3):
        obj.increment_retries()
    assert obj.has_exceeded_max_retries() is True  # >= not >

def test_init_retry_resets_state() -> None:
    obj = ConcreteRetry()
    obj.increment_retries()
    obj._init_retry()  # reset
    assert obj.current_retries == 0
```

`BalanceValidationMixin` tests verify only the stub raises `NotImplementedError` with the correct message.

---

**Testing additions to `strategy_framework/testing/`:**

`TrackedOrderFactory` provides `open_order()` and `filled_order()` static methods. Both return a concrete class satisfying all five `TrackedOrderProtocol` fields: `order_id`, `is_filled`, `is_open`, `filled_amount`, `average_price`. `filled_order()` sets `is_filled=True`, `is_open=False`, `filled_amount=amount`.

---

**Integration test (`tests/integration/test_mixin_composition.py`):**

```python
class CompositeExecutor(RetryMixin, TrailingStopMixin, OrderTrackingMixin):
    # implements RetryHostProtocol + BarrierControlProtocol + OrderTrackingProtocol
    max_retries: int = 3
    ...

def test_composite_executor_initializes_all_mixin_state() -> None: ...
def test_trailing_stop_and_retry_state_independent() -> None: ...
def test_order_tracking_unaffected_by_retry_increment() -> None: ...
def test_init_called_twice_resets_state_safely() -> None: ...  # MRO double-init safety


class PnLWithTrailingStop(PNLCalculatorMixin, TrailingStopMixin):
    # real-world composition: trailing stop reads net_pnl_pct from PNLCalculatorMixin
    ...

def test_trailing_stop_reads_pnl_from_pnl_mixin() -> None: ...
```

---

**Quality gates:** ≥90% coverage, mypy strict, ruff clean — matching Plan 1.

---

## What This Enables for Plan 3

Controller building blocks can import `TrailingStopMixin`, `PNLCalculatorMixin`, `OrderTrackingMixin` directly. Composition without re-implementing the math. The `BalanceValidationMixin` stub interface is established so Plan 3 can reference it by contract.

---

## Source References

- In-tree mixins to port from: `hummingbot/strategy_v2/executors/mixins/`
- Plan 1 composites: `strategy_framework/protocols/composites.py`
- Plan 1 primitives (TrailingStop field names): `strategy_framework/primitives/trailing_stop.py`
  - Use `activation_price_pct` and `trailing_delta_pct` — NOT `activation_price` / `trailing_delta`
- market-simulator BalanceProtocol: `sub-packages/market-simulator/market_simulator/protocols/connector.py`
