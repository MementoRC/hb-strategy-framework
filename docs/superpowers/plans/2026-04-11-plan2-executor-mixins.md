# Plan 2: Executor Mixin Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 7-mixin executor layer to `strategy_framework/mixins/executor/` with protocol-typed `self:` against Plan 1 composites, porting proven algorithms from hummingbot while removing all hummingbot-internal dependencies.

**Architecture:** Hybrid port-and-redesign. Each mixin types `self:` against a *host protocol* (inputs the mixin reads) — distinct from the *output protocol* (what consumers see). Three are deliberate redesigns (ActivationBounds, OrderTracking, Shutdown); three are algorithm ports (Retry, PNL, TrailingStop); one is a stub (BalanceValidation). All protocol changes are amendments to Plan 1 files.

**Tech Stack:** Python 3.10+, Pydantic v2, mypy strict, ruff, pytest (asyncio_mode=auto), pixi.

**Working directory for all commands:** `sub-packages/strategy-framework/`

**Spec:** `docs/superpowers/specs/2026-04-11-plan2-executor-mixins-design.md`

---

## File Map

### Modify (Plan 1 files)
- `strategy_framework/protocols/market.py` — add `get_available_balance`
- `strategy_framework/protocols/composites.py` — 6 amendments (see Task 1)
- `strategy_framework/testing/factories.py` — add `TrackedOrderFactory`
- `strategy_framework/__init__.py` — add mixin exports

### Create (new)
- `strategy_framework/mixins/__init__.py`
- `strategy_framework/mixins/executor/__init__.py`
- `strategy_framework/mixins/executor/retry.py`
- `strategy_framework/mixins/executor/shutdown.py`
- `strategy_framework/mixins/executor/activation.py`
- `strategy_framework/mixins/executor/balance.py`
- `strategy_framework/mixins/executor/order_tracking.py`
- `strategy_framework/mixins/executor/pnl.py`
- `strategy_framework/mixins/executor/trailing_stop.py`
- `tests/unit/mixins/__init__.py`
- `tests/unit/mixins/executor/__init__.py`
- `tests/unit/mixins/executor/test_retry.py`
- `tests/unit/mixins/executor/test_shutdown.py`
- `tests/unit/mixins/executor/test_activation.py`
- `tests/unit/mixins/executor/test_balance.py`
- `tests/unit/mixins/executor/test_order_tracking.py`
- `tests/unit/mixins/executor/test_pnl.py`
- `tests/unit/mixins/executor/test_trailing_stop.py`
- `tests/integration/test_mixin_composition.py`

---

## Task 1: Protocol Amendments

**Files:**
- Modify: `strategy_framework/protocols/market.py`
- Modify: `strategy_framework/protocols/composites.py`

These are the type-system foundations all mixins depend on. No runtime behavior changes — pure Protocol additions and amendments.

- [ ] **Step 1.1: Add `get_available_balance` to `MarketAccessProtocol`**

In `strategy_framework/protocols/market.py`, add one method to `MarketAccessProtocol`:

```python
def get_available_balance(self, currency: str) -> Decimal:  # pragma: no cover
    """Return available (unlocked) balance for the given currency."""
    ...
```

Place it after `get_mid_price`. The full protocol body becomes:

```python
@runtime_checkable
class MarketAccessProtocol(Protocol):
    def place_order(self, order_type: str, side: str, amount: Decimal, price: Decimal) -> str: ...
    def cancel_order(self, order_id: str) -> None: ...
    def get_mid_price(self) -> Decimal: ...
    def get_available_balance(self, currency: str) -> Decimal: ...  # ADD
```

- [ ] **Step 1.2: Amend `composites.py` — 6 changes**

Replace the entire content of `strategy_framework/protocols/composites.py` with:

```python
"""Pre-built composite protocol joins for common mixin requirements.

These combine simple protocols into the exact interface a specific mixin needs.
Mixin methods type `self:` against these composites.

Convention:
- *HostProtocol  — what the HOST must provide (mixin reads these as inputs)
- *Protocol      — what CONSUMERS see on a class that has the mixin (output contract)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from decimal import Decimal

    from strategy_framework.primitives.enums import CloseType, RunnableStatus, TradeType
    from strategy_framework.primitives.trailing_stop import TrailingStop
    from strategy_framework.primitives.triple_barrier import TripleBarrierConfig


# ---------------------------------------------------------------------------
# PNL
# ---------------------------------------------------------------------------


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


@runtime_checkable
class PnLProtocol(Protocol):
    """PnL output contract — what consumers see on a class with PNLCalculatorMixin."""

    @property
    def net_pnl_pct(self) -> Decimal: ...

    @property
    def net_pnl_quote(self) -> Decimal: ...

    @property
    def cum_fees_quote(self) -> Decimal: ...

    @property
    def trade_pnl_pct(self) -> Decimal: ...

    @property
    def trade_pnl_quote(self) -> Decimal: ...  # ADDED vs Plan 1


# ---------------------------------------------------------------------------
# Barrier / TrailingStop
# ---------------------------------------------------------------------------


@runtime_checkable
class BarrierControlProtocol(Protocol):
    """Host protocol for TrailingStopMixin and barrier evaluation."""

    status: RunnableStatus
    close_type: CloseType | None

    @property
    def net_pnl_pct(self) -> Decimal: ...

    @property
    def triple_barrier(self) -> TripleBarrierConfig: ...

    @property
    def trailing_stop(self) -> TrailingStop | None: ...

    @property
    def elapsed_seconds(self) -> float: ...

    def place_close_order(self, close_type: CloseType) -> None: ...


# ---------------------------------------------------------------------------
# Retry
# ---------------------------------------------------------------------------


class RetryHostProtocol(Protocol):
    """What the host must provide for RetryMixin (input contract)."""

    max_retries: int


class RetryProtocol(Protocol):
    """Retry output contract — what consumers see on a class with RetryMixin."""

    current_retries: int  # plain attribute (not @property)
    max_retries: int

    def increment_retries(self) -> None: ...


# ---------------------------------------------------------------------------
# OrderTracking
# ---------------------------------------------------------------------------


class OrderTrackingProtocol(Protocol):
    """Order tracking output contract."""

    @property
    def open_orders(self) -> list[object]: ...

    @property
    def close_orders(self) -> list[object]: ...

    def update_tracked_order(self, order_id: str, **kwargs: object) -> None: ...


# ---------------------------------------------------------------------------
# ActivationBounds
# ---------------------------------------------------------------------------


class ActivationBoundsProtocol(Protocol):
    """Host protocol for ActivationBoundsMixin."""

    entry_price: Decimal
    activation_bounds: tuple[Decimal, Decimal] | None
    # Bounds semantics: (lower_multiplier, upper_multiplier) relative to entry_price.
    # Example: (Decimal("0.99"), Decimal("1.01")) = active when price within 1% of entry.
    # None = always active.
```

- [ ] **Step 1.3: Verify mypy and tests still pass**

```bash
pixi run typecheck
pixi run test
```

Expected: both pass (no existing code broke — all changes are additive except the RetryProtocol attribute form, which is backwards-compatible).

- [ ] **Step 1.4: Commit**

```bash
git add strategy_framework/protocols/market.py strategy_framework/protocols/composites.py
git commit -m "feat(protocols): amend composites and market for Plan 2 mixin layer"
```

---

## Task 2: TrackedOrderFactory

**Files:**
- Modify: `strategy_framework/testing/factories.py`
- Test: `tests/unit/testing/test_factories.py` (existing — add new test)

`TrackedOrderFactory` creates concrete `TrackedOrderProtocol` objects for use in `OrderTrackingMixin` tests. Add it to the existing factories module.

- [ ] **Step 2.1: Write the failing test**

Add to `tests/unit/testing/test_factories.py`:

```python
from decimal import Decimal

from strategy_framework.protocols.order import TrackedOrderProtocol
from strategy_framework.testing.factories import TrackedOrderFactory


def test_open_order_satisfies_protocol() -> None:
    order = TrackedOrderFactory.open_order()
    assert isinstance(order, TrackedOrderProtocol)
    assert order.order_id == "mock_0001"
    assert order.is_open is True
    assert order.is_filled is False
    assert order.filled_amount == Decimal("0")
    assert order.average_price == Decimal("100.0")


def test_filled_order_satisfies_protocol() -> None:
    order = TrackedOrderFactory.filled_order(amount=Decimal("2.5"), price=Decimal("50000"))
    assert isinstance(order, TrackedOrderProtocol)
    assert order.is_filled is True
    assert order.is_open is False
    assert order.filled_amount == Decimal("2.5")
    assert order.average_price == Decimal("50000")


def test_open_order_custom_id() -> None:
    order = TrackedOrderFactory.open_order(order_id="custom_001")
    assert order.order_id == "custom_001"
```

- [ ] **Step 2.2: Run to verify failure**

```bash
pixi run test tests/unit/testing/test_factories.py -k "tracked" -v
```

Expected: `AttributeError: module has no attribute 'TrackedOrderFactory'`

- [ ] **Step 2.3: Add `TrackedOrderFactory` to `factories.py`**

Add at the bottom of `strategy_framework/testing/factories.py`:

```python
from strategy_framework.protocols.order import TrackedOrderProtocol


class _MockTrackedOrder:
    """Concrete implementation of TrackedOrderProtocol for tests."""

    def __init__(
        self,
        order_id: str,
        is_filled: bool,
        is_open: bool,
        filled_amount: Decimal,
        average_price: Decimal,
    ) -> None:
        self.order_id = order_id
        self.is_filled = is_filled
        self.is_open = is_open
        self.filled_amount = filled_amount
        self.average_price = average_price


class TrackedOrderFactory:
    """Factory for creating mock TrackedOrderProtocol instances."""

    @staticmethod
    def open_order(
        order_id: str = "mock_0001",
        amount: Decimal = Decimal("1.0"),
        price: Decimal = Decimal("100.0"),
        side: str = "BUY",  # noqa: ARG004 — reserved for future asymmetric bounds tests
    ) -> TrackedOrderProtocol:
        """Return a mock open (unfilled) order."""
        return _MockTrackedOrder(  # type: ignore[return-value]
            order_id=order_id,
            is_filled=False,
            is_open=True,
            filled_amount=Decimal("0"),
            average_price=price,
        )

    @staticmethod
    def filled_order(
        order_id: str = "mock_0001",
        amount: Decimal = Decimal("1.0"),
        price: Decimal = Decimal("100.0"),
    ) -> TrackedOrderProtocol:
        """Return a mock fully-filled order. filled_amount=amount, is_filled=True."""
        return _MockTrackedOrder(  # type: ignore[return-value]
            order_id=order_id,
            is_filled=True,
            is_open=False,
            filled_amount=amount,
            average_price=price,
        )
```

Also add `Decimal` import at top of file if not present:
```python
from decimal import Decimal
```

- [ ] **Step 2.4: Run tests to verify pass**

```bash
pixi run test tests/unit/testing/test_factories.py -k "tracked" -v
```

Expected: 3 tests PASS.

- [ ] **Step 2.5: Commit**

```bash
git add strategy_framework/testing/factories.py tests/unit/testing/test_factories.py
git commit -m "feat(testing): add TrackedOrderFactory for mixin tests"
```

---

## Task 3: Module Scaffolding

**Files:** Create `__init__.py` files for the mixin module hierarchy.

- [ ] **Step 3.1: Create directory `__init__.py` files**

`strategy_framework/mixins/__init__.py`:
```python
"""Executor and controller mixin layer."""
```

`strategy_framework/mixins/executor/__init__.py`:
```python
"""Protocol-typed executor mixins.

Each mixin types self: against a host protocol from strategy_framework.protocols.composites.
Import the mixin you need; compose with MRO-safe _init_<mixin>() pattern.

Example:
    class MyExecutor(RetryMixin, TrailingStopMixin):
        max_retries: int = 3
        ...

        def __init__(self) -> None:
            self._init_retry()
            self._init_trailing_stop()
"""

from strategy_framework.mixins.executor.activation import ActivationBoundsMixin
from strategy_framework.mixins.executor.balance import BalanceValidationMixin
from strategy_framework.mixins.executor.order_tracking import OrderTrackingMixin
from strategy_framework.mixins.executor.pnl import PNLCalculatorMixin
from strategy_framework.mixins.executor.retry import RetryMixin
from strategy_framework.mixins.executor.shutdown import ShutdownMixin
from strategy_framework.mixins.executor.trailing_stop import TrailingStopMixin

__all__ = [
    "ActivationBoundsMixin",
    "BalanceValidationMixin",
    "OrderTrackingMixin",
    "PNLCalculatorMixin",
    "RetryMixin",
    "ShutdownMixin",
    "TrailingStopMixin",
]
```

`tests/unit/mixins/__init__.py`: empty file
`tests/unit/mixins/executor/__init__.py`: empty file

- [ ] **Step 3.2: Create placeholder mixin files (will be filled in subsequent tasks)**

Each file should just have the import header and a `pass` class for now, so the `__init__.py` imports don't break. This is just scaffolding — each task below will replace these.

Each placeholder must define the actual class name (so the `executor/__init__.py` imports don't fail at collection time):

```python
# retry.py placeholder
"""RetryMixin — retry count tracking and max-retries evaluation."""
class RetryMixin: pass
```

Repeat the same pattern for all 7 files (`ShutdownMixin`, `ActivationBoundsMixin`, `BalanceValidationMixin`, `OrderTrackingMixin`, `PNLCalculatorMixin`, `TrailingStopMixin`). Each task below replaces the placeholder with the real implementation.

- [ ] **Step 3.3: Verify import structure works**

```bash
pixi run test tests/ --collect-only 2>&1 | head -5
```

Expected: collection succeeds (0 errors).

---

## Task 4: RetryMixin

**Files:**
- Create: `strategy_framework/mixins/executor/retry.py`
- Create: `tests/unit/mixins/executor/test_retry.py`

**Algorithm:** Port from `hummingbot/strategy_v2/executors/mixins/retry.py`. Replaces `max_retries` parameter injection with `RetryHostProtocol.max_retries`. Changes boundary from `>` to `>=`.

- [ ] **Step 4.1: Write the failing tests**

`tests/unit/mixins/executor/test_retry.py`:

```python
"""Tests for RetryMixin."""

from __future__ import annotations

import pytest

from strategy_framework.mixins.executor.retry import RetryMixin
from strategy_framework.protocols.composites import RetryHostProtocol


class ConcreteRetry(RetryMixin):
    """Minimal concrete class satisfying RetryHostProtocol."""

    max_retries: int = 3

    def __init__(self) -> None:
        self._init_retry()


def test_init_sets_current_retries_to_zero() -> None:
    obj = ConcreteRetry()
    assert obj.current_retries == 0


def test_increment_retries_advances_counter() -> None:
    obj = ConcreteRetry()
    obj.increment_retries()
    assert obj.current_retries == 1


def test_increment_retries_accumulates() -> None:
    obj = ConcreteRetry()
    obj.increment_retries()
    obj.increment_retries()
    assert obj.current_retries == 2


def test_has_not_exceeded_below_limit() -> None:
    obj = ConcreteRetry()
    obj.increment_retries()  # 1 of 3
    assert obj.has_exceeded_max_retries() is False


def test_has_exceeded_at_exactly_max_retries() -> None:
    obj = ConcreteRetry()
    for _ in range(3):
        obj.increment_retries()
    assert obj.has_exceeded_max_retries() is True  # >= not >


def test_has_exceeded_beyond_max_retries() -> None:
    obj = ConcreteRetry()
    for _ in range(5):
        obj.increment_retries()
    assert obj.has_exceeded_max_retries() is True


def test_init_retry_resets_state() -> None:
    obj = ConcreteRetry()
    obj.increment_retries()
    obj.increment_retries()
    obj._init_retry()  # reset
    assert obj.current_retries == 0


def test_zero_max_retries_exceeds_immediately() -> None:
    class ZeroRetry(RetryMixin):
        max_retries: int = 0
        def __init__(self) -> None:
            self._init_retry()

    obj = ZeroRetry()
    assert obj.has_exceeded_max_retries() is True


def test_satisfies_retry_protocol() -> None:
    from strategy_framework.protocols.composites import RetryProtocol
    obj = ConcreteRetry()
    assert isinstance(obj, RetryProtocol)
```

- [ ] **Step 4.2: Run to verify failure**

```bash
pixi run test tests/unit/mixins/executor/test_retry.py -v
```

Expected: `ImportError` or `AttributeError` — retry.py is a placeholder.

- [ ] **Step 4.3: Write `RetryMixin`**

`strategy_framework/mixins/executor/retry.py`:

```python
"""RetryMixin — retry count tracking and max-retries evaluation.

Self-typed against RetryHostProtocol. The host must provide max_retries: int.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from strategy_framework.protocols.composites import RetryHostProtocol


class RetryMixin:
    """Mixin for retry count management.

    Usage:
        class MyExecutor(RetryMixin):
            max_retries: int = 3

            def __init__(self) -> None:
                self._init_retry()

    MRO init order: call _init_retry() after all super().__init__() calls.
    Calling _init_retry() twice resets state (safe in diamond MRO).
    """

    def _init_retry(self: RetryHostProtocol) -> None:  # type: ignore[misc]
        """Initialize retry state. Call from __init__ after super().__init__()."""
        self.current_retries: int = 0  # type: ignore[attr-defined]

    def increment_retries(self: RetryHostProtocol) -> None:  # type: ignore[misc]
        """Increment the retry counter by one."""
        self.current_retries += 1  # type: ignore[attr-defined]

    def has_exceeded_max_retries(self: RetryHostProtocol) -> bool:  # type: ignore[misc]
        """Return True when current_retries >= max_retries.

        Note: uses >= (fires at exactly max_retries), unlike the in-tree version
        which uses > (fires at max_retries + 1).
        """
        return self.current_retries >= self.max_retries  # type: ignore[attr-defined]
```

- [ ] **Step 4.4: Run tests**

```bash
pixi run test tests/unit/mixins/executor/test_retry.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 4.5: Run typecheck and lint**

```bash
pixi run typecheck
pixi run lint
```

Expected: clean.

- [ ] **Step 4.6: Commit**

```bash
git add strategy_framework/mixins/executor/retry.py tests/unit/mixins/executor/test_retry.py
git commit -m "feat(mixins): add RetryMixin with protocol-typed self"
```

---

## Task 5: ShutdownMixin

**Files:**
- Create: `strategy_framework/mixins/executor/shutdown.py`
- Create: `tests/unit/mixins/executor/test_shutdown.py`

**Design:** Synchronous state management only. Manages `_shutdown_requested` flag. `has_pending_orders` is abstract — host overrides it. The async poll loop (in hummingbot's version) is the host executor's responsibility.

- [ ] **Step 5.1: Write the failing tests**

`tests/unit/mixins/executor/test_shutdown.py`:

```python
"""Tests for ShutdownMixin."""

from __future__ import annotations

import pytest

from strategy_framework.mixins.executor.shutdown import ShutdownMixin


class ConcreteShutdown(ShutdownMixin):
    """Concrete shutdown with controllable pending-order state."""

    def __init__(self, pending: bool = False) -> None:
        self._pending = pending
        self._init_shutdown()

    @property
    def has_pending_orders(self) -> bool:
        return self._pending


def test_init_shutdown_requested_false() -> None:
    obj = ConcreteShutdown()
    assert obj.shutdown_requested is False


def test_request_shutdown_sets_flag() -> None:
    obj = ConcreteShutdown()
    obj.request_shutdown()
    assert obj.shutdown_requested is True


def test_request_shutdown_idempotent() -> None:
    obj = ConcreteShutdown()
    obj.request_shutdown()
    obj.request_shutdown()
    assert obj.shutdown_requested is True


def test_has_pending_orders_delegates_to_host() -> None:
    obj_with = ConcreteShutdown(pending=True)
    obj_without = ConcreteShutdown(pending=False)
    assert obj_with.has_pending_orders is True
    assert obj_without.has_pending_orders is False


def test_init_shutdown_resets_state() -> None:
    obj = ConcreteShutdown()
    obj.request_shutdown()
    obj._init_shutdown()
    assert obj.shutdown_requested is False


def test_has_pending_orders_abstract_raises_if_not_overridden() -> None:
    """ShutdownMixin.has_pending_orders must be overridden."""
    obj = ShutdownMixin()
    obj._init_shutdown()
    with pytest.raises(NotImplementedError):
        _ = obj.has_pending_orders
```

- [ ] **Step 5.2: Run to verify failure**

```bash
pixi run test tests/unit/mixins/executor/test_shutdown.py -v
```

Expected: ImportError or AttributeError.

- [ ] **Step 5.3: Write `ShutdownMixin`**

`strategy_framework/mixins/executor/shutdown.py`:

```python
"""ShutdownMixin — graceful shutdown state management.

Provides shutdown flag + has_pending_orders abstract property.
The async poll loop is the host executor's responsibility.
"""

from __future__ import annotations


class ShutdownMixin:
    """Mixin for graceful shutdown state management.

    Usage:
        class MyExecutor(ShutdownMixin):
            def __init__(self) -> None:
                self._init_shutdown()

            @property
            def has_pending_orders(self) -> bool:
                return len(self._open_orders) > 0

        # In the executor's async loop:
        if self.shutdown_requested and not self.has_pending_orders:
            self._declare_done()

    MRO init order: call _init_shutdown() after all super().__init__() calls.
    Calling _init_shutdown() twice resets state (safe in diamond MRO).
    """

    def _init_shutdown(self) -> None:
        """Initialize shutdown state. Call from __init__ after super().__init__()."""
        self._shutdown_requested: bool = False

    def request_shutdown(self) -> None:
        """Signal that a graceful shutdown has been requested."""
        self._shutdown_requested = True

    @property
    def shutdown_requested(self) -> bool:
        """True if request_shutdown() has been called."""
        return self._shutdown_requested

    @property
    def has_pending_orders(self) -> bool:
        """True if there are orders still open/pending.

        Override in the host executor to inspect its own order state.
        The executor's shutdown loop should wait until this returns False.
        """
        raise NotImplementedError(
            "ShutdownMixin.has_pending_orders must be overridden in the host class "
            "to inspect its own order state."
        )
```

- [ ] **Step 5.4: Run tests**

```bash
pixi run test tests/unit/mixins/executor/test_shutdown.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5.5: Commit**

```bash
git add strategy_framework/mixins/executor/shutdown.py tests/unit/mixins/executor/test_shutdown.py
git commit -m "feat(mixins): add ShutdownMixin"
```

---

## Task 6: ActivationBoundsMixin

**Files:**
- Create: `strategy_framework/mixins/executor/activation.py`
- Create: `tests/unit/mixins/executor/test_activation.py`

**Design (deliberate redesign):** Pure function — caller provides `current_price`, mixin checks bounds. No market dependency. `activation_bounds = None` means always active. `activation_bounds = (lower_mult, upper_mult)` defines the range as `entry_price * lower_mult <= current_price <= entry_price * upper_mult`.

- [ ] **Step 6.1: Write the failing tests**

`tests/unit/mixins/executor/test_activation.py`:

```python
"""Tests for ActivationBoundsMixin."""

from __future__ import annotations

from decimal import Decimal

from strategy_framework.mixins.executor.activation import ActivationBoundsMixin


class ConcreteActivation(ActivationBoundsMixin):
    def __init__(
        self,
        entry_price: Decimal,
        activation_bounds: tuple[Decimal, Decimal] | None,
    ) -> None:
        self.entry_price = entry_price
        self.activation_bounds = activation_bounds


ENTRY = Decimal("100")
BOUNDS = (Decimal("0.99"), Decimal("1.01"))  # ±1%


def test_none_bounds_always_active() -> None:
    obj = ConcreteActivation(ENTRY, None)
    assert obj.is_within_activation_bounds(Decimal("50")) is True
    assert obj.is_within_activation_bounds(Decimal("200")) is True


def test_within_bounds_lower_edge() -> None:
    obj = ConcreteActivation(ENTRY, BOUNDS)
    assert obj.is_within_activation_bounds(Decimal("99")) is True  # exactly lower bound


def test_within_bounds_upper_edge() -> None:
    obj = ConcreteActivation(ENTRY, BOUNDS)
    assert obj.is_within_activation_bounds(Decimal("101")) is True  # exactly upper bound


def test_below_lower_bound() -> None:
    obj = ConcreteActivation(ENTRY, BOUNDS)
    assert obj.is_within_activation_bounds(Decimal("98.99")) is False


def test_above_upper_bound() -> None:
    obj = ConcreteActivation(ENTRY, BOUNDS)
    assert obj.is_within_activation_bounds(Decimal("101.01")) is False


def test_at_entry_price() -> None:
    obj = ConcreteActivation(ENTRY, BOUNDS)
    assert obj.is_within_activation_bounds(ENTRY) is True


def test_tight_bounds() -> None:
    tight = (Decimal("1.0"), Decimal("1.0"))  # only exactly at entry
    obj = ConcreteActivation(ENTRY, tight)
    assert obj.is_within_activation_bounds(Decimal("100")) is True
    assert obj.is_within_activation_bounds(Decimal("100.01")) is False
```

- [ ] **Step 6.2: Run to verify failure**

```bash
pixi run test tests/unit/mixins/executor/test_activation.py -v
```

- [ ] **Step 6.3: Write `ActivationBoundsMixin`**

`strategy_framework/mixins/executor/activation.py`:

```python
"""ActivationBoundsMixin — activation price bounds check.

Deliberate redesign from the in-tree version:
- Caller provides current_price (no internal market call)
- Pure function — no state, no _init_ needed
- Side/order-type asymmetry dropped (callers needing this can subclass)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from decimal import Decimal

    from strategy_framework.protocols.composites import ActivationBoundsProtocol


class ActivationBoundsMixin:
    """Mixin for checking if market price is within activation bounds.

    Usage:
        class MyExecutor(ActivationBoundsMixin):
            entry_price: Decimal = Decimal("100")
            activation_bounds: tuple[Decimal, Decimal] | None = (
                Decimal("0.99"), Decimal("1.01")
            )

        # In control loop:
        mid = self.market.get_mid_price()
        if self.is_within_activation_bounds(mid):
            self._activate()

    No state, no _init_ required.
    """

    def is_within_activation_bounds(
        self: ActivationBoundsProtocol,  # type: ignore[misc]
        current_price: Decimal,
    ) -> bool:
        """Return True if current_price is within activation bounds.

        If activation_bounds is None, always returns True (always active).
        Bounds are (lower_multiplier, upper_multiplier) relative to entry_price:
            active when entry_price * lower <= current_price <= entry_price * upper
        """
        if self.activation_bounds is None:
            return True
        lower_mult, upper_mult = self.activation_bounds
        lower = self.entry_price * lower_mult
        upper = self.entry_price * upper_mult
        return lower <= current_price <= upper
```

- [ ] **Step 6.4: Run tests**

```bash
pixi run test tests/unit/mixins/executor/test_activation.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 6.5: Commit**

```bash
git add strategy_framework/mixins/executor/activation.py tests/unit/mixins/executor/test_activation.py
git commit -m "feat(mixins): add ActivationBoundsMixin (pure function, no market dep)"
```

---

## Task 7: BalanceValidationMixin

**Files:**
- Create: `strategy_framework/mixins/executor/balance.py`
- Create: `tests/unit/mixins/executor/test_balance.py`

**Design:** Stub only. Raises `NotImplementedError` with a clear message pointing to the market-simulator adapter. Tests verify only the stub behavior.

- [ ] **Step 7.1: Write the failing tests**

`tests/unit/mixins/executor/test_balance.py`:

```python
"""Tests for BalanceValidationMixin (stub)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from strategy_framework.mixins.executor.balance import BalanceValidationMixin


class ConcreteBalance(BalanceValidationMixin):
    pass


def test_validate_balance_raises_not_implemented() -> None:
    obj = ConcreteBalance()
    with pytest.raises(NotImplementedError):
        obj.validate_balance("USDT", Decimal("1000"))


def test_not_implemented_message_mentions_adapter() -> None:
    obj = ConcreteBalance()
    with pytest.raises(NotImplementedError, match="get_available_balance"):
        obj.validate_balance("USDT", Decimal("1000"))


def test_not_implemented_message_mentions_market_simulator() -> None:
    obj = ConcreteBalance()
    with pytest.raises(NotImplementedError, match="market-simulator"):
        obj.validate_balance("BTC", Decimal("0.1"))
```

- [ ] **Step 7.2: Run to verify failure**

```bash
pixi run test tests/unit/mixins/executor/test_balance.py -v
```

- [ ] **Step 7.3: Write `BalanceValidationMixin`**

`strategy_framework/mixins/executor/balance.py`:

```python
"""BalanceValidationMixin — balance check before order placement.

STUB: raises NotImplementedError. Implement when a market adapter providing
MarketAccessProtocol.get_available_balance() exists (hb-market-simulator or
live-market sub-package).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from decimal import Decimal

    from strategy_framework.protocols.market import MarketAccessProtocol


class BalanceValidationMixin:
    """Stub mixin for pre-order balance validation.

    Will be implemented once hb-market-simulator or a live-market sub-package
    provides a concrete MarketAccessProtocol.get_available_balance() adapter.
    """

    def validate_balance(
        self: MarketAccessProtocol,  # type: ignore[misc]
        currency: str,
        amount: Decimal,
    ) -> bool:
        """Return True if sufficient balance is available.

        STUB — not yet implemented.
        """
        raise NotImplementedError(
            "BalanceValidationMixin.validate_balance requires a concrete market "
            "adapter implementing MarketAccessProtocol.get_available_balance(). "
            "See hb-market-simulator BalanceProtocol for the expected interface. "
            "Implement this when hb-market-simulator or live-market sub-package "
            "provides the adapter."
        )
```

- [ ] **Step 7.4: Run tests**

```bash
pixi run test tests/unit/mixins/executor/test_balance.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 7.5: Commit**

```bash
git add strategy_framework/mixins/executor/balance.py tests/unit/mixins/executor/test_balance.py
git commit -m "feat(mixins): add BalanceValidationMixin stub"
```

---

## Task 8: OrderTrackingMixin

**Files:**
- Create: `strategy_framework/mixins/executor/order_tracking.py`
- Create: `tests/unit/mixins/executor/test_order_tracking.py`

**Design (deliberate redesign):** Lifts full order list management into the mixin. In-tree version only did order-ID matching. Uses `TrackedOrderFactory` for tests.

- [ ] **Step 8.1: Write the failing tests**

`tests/unit/mixins/executor/test_order_tracking.py`:

```python
"""Tests for OrderTrackingMixin."""

from __future__ import annotations

from decimal import Decimal

import pytest

from strategy_framework.mixins.executor.order_tracking import OrderTrackingMixin
from strategy_framework.testing.factories import TrackedOrderFactory


class ConcreteTracking(OrderTrackingMixin):
    def __init__(self) -> None:
        self._init_order_tracking()


def test_init_empty_lists() -> None:
    obj = ConcreteTracking()
    assert obj.open_orders == []
    assert obj.close_orders == []


def test_add_open_order() -> None:
    obj = ConcreteTracking()
    order = TrackedOrderFactory.open_order(order_id="buy_001")
    obj.add_open_order(order)
    assert len(obj.open_orders) == 1
    assert obj.open_orders[0].order_id == "buy_001"


def test_add_close_order() -> None:
    obj = ConcreteTracking()
    order = TrackedOrderFactory.open_order(order_id="sell_001")
    obj.add_close_order(order)
    assert len(obj.close_orders) == 1


def test_get_filled_open_orders_empty_when_none_filled() -> None:
    obj = ConcreteTracking()
    obj.add_open_order(TrackedOrderFactory.open_order())
    assert obj.get_filled_open_orders() == []


def test_get_filled_open_orders_returns_filled() -> None:
    obj = ConcreteTracking()
    obj.add_open_order(TrackedOrderFactory.open_order(order_id="unfilled"))
    obj.add_open_order(TrackedOrderFactory.filled_order(order_id="filled"))
    filled = obj.get_filled_open_orders()
    assert len(filled) == 1
    assert filled[0].order_id == "filled"


def test_get_open_order_found() -> None:
    obj = ConcreteTracking()
    obj.add_open_order(TrackedOrderFactory.open_order(order_id="target"))
    result = obj.get_open_order("target")
    assert result is not None
    assert result.order_id == "target"


def test_get_open_order_not_found_returns_none() -> None:
    obj = ConcreteTracking()
    assert obj.get_open_order("nonexistent") is None


def test_update_tracked_order_updates_kwargs() -> None:
    obj = ConcreteTracking()
    order = TrackedOrderFactory.open_order(order_id="upd_001")
    obj.add_open_order(order)
    # update_tracked_order is a no-op in the base; verify it doesn't raise
    obj.update_tracked_order("upd_001", exchange_order_id="exch_123")


def test_init_order_tracking_resets_state() -> None:
    obj = ConcreteTracking()
    obj.add_open_order(TrackedOrderFactory.open_order())
    obj._init_order_tracking()
    assert obj.open_orders == []
    assert obj.close_orders == []


def test_multiple_open_orders() -> None:
    obj = ConcreteTracking()
    for i in range(3):
        obj.add_open_order(TrackedOrderFactory.open_order(order_id=f"order_{i:03d}"))
    assert len(obj.open_orders) == 3
```

- [ ] **Step 8.2: Run to verify failure**

```bash
pixi run test tests/unit/mixins/executor/test_order_tracking.py -v
```

- [ ] **Step 8.3: Write `OrderTrackingMixin`**

`strategy_framework/mixins/executor/order_tracking.py`:

```python
"""OrderTrackingMixin — open/close order list management.

Deliberate redesign from the in-tree version, which only matched order IDs.
This mixin owns the full order list and provides lookup/filtering utilities.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from strategy_framework.protocols.composites import OrderTrackingProtocol
    from strategy_framework.protocols.order import TrackedOrderProtocol


class OrderTrackingMixin:
    """Mixin for managing open and close order lists.

    Usage:
        class MyExecutor(OrderTrackingMixin):
            def __init__(self) -> None:
                self._init_order_tracking()

    MRO init order: call _init_order_tracking() after all super().__init__() calls.
    Calling _init_order_tracking() twice resets lists (safe in diamond MRO).
    """

    def _init_order_tracking(self: OrderTrackingProtocol) -> None:  # type: ignore[misc]
        """Initialize order tracking state. Call from __init__ after super().__init__()."""
        self._open_orders: list[TrackedOrderProtocol] = []  # type: ignore[attr-defined]
        self._close_orders: list[TrackedOrderProtocol] = []  # type: ignore[attr-defined]

    @property
    def open_orders(self: OrderTrackingProtocol) -> list[TrackedOrderProtocol]:  # type: ignore[misc]
        """List of currently open (entry) orders."""
        return self._open_orders  # type: ignore[attr-defined]

    @property
    def close_orders(self: OrderTrackingProtocol) -> list[TrackedOrderProtocol]:  # type: ignore[misc]
        """List of close (exit) orders."""
        return self._close_orders  # type: ignore[attr-defined]

    def add_open_order(
        self: OrderTrackingProtocol,  # type: ignore[misc]
        order: TrackedOrderProtocol,
    ) -> None:
        """Append an open order to the tracking list."""
        self._open_orders.append(order)  # type: ignore[attr-defined]

    def add_close_order(
        self: OrderTrackingProtocol,  # type: ignore[misc]
        order: TrackedOrderProtocol,
    ) -> None:
        """Append a close order to the tracking list."""
        self._close_orders.append(order)  # type: ignore[attr-defined]

    def update_tracked_order(
        self: OrderTrackingProtocol,  # type: ignore[misc]
        order_id: str,
        **kwargs: object,
    ) -> None:
        """Update tracked order state by order_id.

        Base implementation is a no-op. Override in the host to enrich order
        state (e.g., set exchange_order_id, update fill amounts).
        """

    def get_filled_open_orders(
        self: OrderTrackingProtocol,  # type: ignore[misc]
    ) -> list[TrackedOrderProtocol]:
        """Return open orders that are fully filled."""
        return [o for o in self._open_orders if o.is_filled]  # type: ignore[attr-defined]

    def get_open_order(
        self: OrderTrackingProtocol,  # type: ignore[misc]
        order_id: str,
    ) -> TrackedOrderProtocol | None:
        """Return the open order with the given order_id, or None."""
        orders = self._open_orders  # type: ignore[attr-defined]
        return next((o for o in orders if o.order_id == order_id), None)
```

- [ ] **Step 8.4: Run tests**

```bash
pixi run test tests/unit/mixins/executor/test_order_tracking.py -v
```

Expected: all 10 tests PASS.

- [ ] **Step 8.5: Commit**

```bash
git add strategy_framework/mixins/executor/order_tracking.py tests/unit/mixins/executor/test_order_tracking.py
git commit -m "feat(mixins): add OrderTrackingMixin with list management"
```

---

## Task 9: PNLCalculatorMixin

**Files:**
- Create: `strategy_framework/mixins/executor/pnl.py`
- Create: `tests/unit/mixins/executor/test_pnl.py`

**Algorithm:** Port from `hummingbot/strategy_v2/executors/mixins/pnl_calculator.py`. Replace template methods with `PnLHostProtocol` property reads. Expose all values as `@property` (not methods as in hummingbot).

- [ ] **Step 9.1: Write the failing tests**

`tests/unit/mixins/executor/test_pnl.py`:

```python
"""Tests for PNLCalculatorMixin."""

from __future__ import annotations

from decimal import Decimal

import pytest

from strategy_framework.mixins.executor.pnl import PNLCalculatorMixin
from strategy_framework.primitives.enums import TradeType


def _make_executor(
    entry: str,
    close: str,
    filled_quote: str,
    side: TradeType,
    fees: str = "0",
) -> PNLCalculatorMixin:
    class ConcretePNL(PNLCalculatorMixin):
        @property
        def entry_price(self) -> Decimal:
            return Decimal(entry)

        @property
        def close_price(self) -> Decimal:
            return Decimal(close)

        @property
        def open_filled_amount_quote(self) -> Decimal:
            return Decimal(filled_quote)

        @property
        def trade_side(self) -> TradeType:
            return side

        @property
        def cum_fees_raw(self) -> Decimal:
            return Decimal(fees)

    return ConcretePNL()


def test_trade_pnl_pct_buy_profit() -> None:
    obj = _make_executor("100", "110", "1000", TradeType.BUY)
    assert obj.trade_pnl_pct == Decimal("0.1")


def test_trade_pnl_pct_buy_loss() -> None:
    obj = _make_executor("100", "90", "1000", TradeType.BUY)
    assert obj.trade_pnl_pct == Decimal("-0.1")


def test_trade_pnl_pct_sell_profit() -> None:
    obj = _make_executor("100", "90", "1000", TradeType.SELL)
    assert obj.trade_pnl_pct == Decimal("0.1")


def test_trade_pnl_pct_sell_loss() -> None:
    obj = _make_executor("100", "110", "1000", TradeType.SELL)
    assert obj.trade_pnl_pct == Decimal("-0.1")


def test_trade_pnl_pct_zero_entry_returns_zero() -> None:
    obj = _make_executor("0", "100", "1000", TradeType.BUY)
    assert obj.trade_pnl_pct == Decimal("0")


def test_trade_pnl_quote() -> None:
    obj = _make_executor("100", "110", "1000", TradeType.BUY)
    # trade_pnl_pct=0.1, filled_quote=1000 → trade_pnl_quote=100
    assert obj.trade_pnl_quote == Decimal("100")


def test_cum_fees_quote_reflects_raw_fees() -> None:
    obj = _make_executor("100", "110", "1000", TradeType.BUY, fees="5")
    assert obj.cum_fees_quote == Decimal("5")


def test_net_pnl_quote_deducts_fees() -> None:
    obj = _make_executor("100", "110", "1000", TradeType.BUY, fees="5")
    assert obj.net_pnl_quote == Decimal("95")


def test_net_pnl_pct_deducts_fees() -> None:
    # trade_pnl_pct=0.1, fees=5 on 1000 filled → fee_pct=0.005
    obj = _make_executor("100", "110", "1000", TradeType.BUY, fees="5")
    assert obj.net_pnl_pct == Decimal("0.095")


def test_net_pnl_pct_zero_filled_returns_zero() -> None:
    obj = _make_executor("100", "110", "0", TradeType.BUY)
    assert obj.net_pnl_pct == Decimal("0")
```

- [ ] **Step 9.2: Run to verify failure**

```bash
pixi run test tests/unit/mixins/executor/test_pnl.py -v
```

- [ ] **Step 9.3: Write `PNLCalculatorMixin`**

`strategy_framework/mixins/executor/pnl.py`:

```python
"""PNLCalculatorMixin — trade PnL calculation using protocol-typed host inputs.

Ported from hummingbot/strategy_v2/executors/mixins/pnl_calculator.py.
Template methods replaced with PnLHostProtocol property reads.
All values exposed as @property (not methods as in hummingbot).
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from strategy_framework.primitives.enums import TradeType
    from strategy_framework.protocols.composites import PnLHostProtocol


class PNLCalculatorMixin:
    """Mixin for single-entry/exit PnL calculation.

    Applies to executors with one open leg and one close leg
    (e.g., position, DCA entry). Does NOT apply to grid or arbitrage.

    Usage:
        class MyExecutor(PNLCalculatorMixin):
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

    No state, no _init_ required — all properties are pure computations.
    """

    @property
    def trade_pnl_pct(self: PnLHostProtocol) -> Decimal:  # type: ignore[misc]
        """PnL percentage excluding fees.

        BUY:  (close - entry) / entry
        SELL: (entry - close) / entry
        Returns 0 if entry_price is 0 (no fill yet).
        """
        from strategy_framework.primitives.enums import TradeType

        if self.entry_price == Decimal("0"):
            return Decimal("0")
        if self.trade_side == TradeType.BUY:
            return (self.close_price - self.entry_price) / self.entry_price
        return (self.entry_price - self.close_price) / self.entry_price

    @property
    def trade_pnl_quote(self: PnLHostProtocol) -> Decimal:  # type: ignore[misc]
        """PnL in quote currency excluding fees."""
        return self.trade_pnl_pct * self.open_filled_amount_quote

    @property
    def cum_fees_quote(self: PnLHostProtocol) -> Decimal:  # type: ignore[misc]
        """Cumulative fees in quote currency."""
        return self.cum_fees_raw

    @property
    def net_pnl_quote(self: PnLHostProtocol) -> Decimal:  # type: ignore[misc]
        """Net PnL in quote currency after fees."""
        return self.trade_pnl_quote - self.cum_fees_quote

    @property
    def net_pnl_pct(self: PnLHostProtocol) -> Decimal:  # type: ignore[misc]
        """Net PnL percentage after fees.

        Returns 0 if open_filled_amount_quote is 0 (no fill yet).
        """
        if self.open_filled_amount_quote <= Decimal("0"):
            return Decimal("0")
        return self.net_pnl_quote / self.open_filled_amount_quote
```

- [ ] **Step 9.4: Run tests**

```bash
pixi run test tests/unit/mixins/executor/test_pnl.py -v
```

Expected: all 10 tests PASS.

- [ ] **Step 9.5: Commit**

```bash
git add strategy_framework/mixins/executor/pnl.py tests/unit/mixins/executor/test_pnl.py
git commit -m "feat(mixins): add PNLCalculatorMixin with PnLHostProtocol typing"
```

---

## Task 10: TrailingStopMixin

**Files:**
- Create: `strategy_framework/mixins/executor/trailing_stop.py`
- Create: `tests/unit/mixins/executor/test_trailing_stop.py`

**Algorithm:** Port ratchet from `hummingbot/strategy_v2/executors/mixins/trailing_stop.py`. Key adaptation: uses `trailing_stop.activation_price_pct` and `trailing_stop.trailing_delta_pct` (with `_pct` suffix — different from in-tree `activation_price`/`trailing_delta`). Tracks PNL-pct-based trigger (not price-based), reading `self.net_pnl_pct` from `BarrierControlProtocol`.

- [ ] **Step 10.1: Write the failing tests**

`tests/unit/mixins/executor/test_trailing_stop.py`:

```python
"""Tests for TrailingStopMixin."""

from __future__ import annotations

from decimal import Decimal

import pytest

from strategy_framework.mixins.executor.trailing_stop import TrailingStopMixin
from strategy_framework.primitives.enums import CloseType, RunnableStatus
from strategy_framework.primitives.trailing_stop import TrailingStop
from strategy_framework.primitives.triple_barrier import TripleBarrierConfig


class ConcreteTrailing(TrailingStopMixin):
    """Concrete executor with controllable PnL and trailing stop config."""

    def __init__(
        self,
        trailing_stop: TrailingStop | None,
        initial_pnl_pct: Decimal = Decimal("0"),
    ) -> None:
        self._trailing_stop_cfg = trailing_stop
        self._pnl_pct = initial_pnl_pct
        self.status = RunnableStatus.RUNNING
        self.close_type: CloseType | None = None
        self.elapsed_seconds: float = 0.0
        self._init_trailing_stop()

    @property
    def net_pnl_pct(self) -> Decimal:
        return self._pnl_pct

    @property
    def trailing_stop(self) -> TrailingStop | None:
        return self._trailing_stop_cfg

    @property
    def triple_barrier(self) -> TripleBarrierConfig:
        return TripleBarrierConfig(stop_loss=Decimal("0.05"), take_profit=Decimal("0.1"))

    def place_close_order(self, close_type: CloseType) -> None:
        self.close_type = close_type


TS_CONFIG = TrailingStop(
    activation_price_pct=Decimal("0.02"),  # activates at +2% PnL
    trailing_delta_pct=Decimal("0.01"),    # trigger = pnl - 1%
)


def test_init_state() -> None:
    obj = ConcreteTrailing(TS_CONFIG)
    assert obj.trailing_stop_activated is False
    assert obj.trailing_stop_triggered is False


def test_not_triggered_without_config() -> None:
    obj = ConcreteTrailing(None)
    obj.update_trailing_stop(Decimal("105"))
    assert obj.trailing_stop_triggered is False


def test_not_activated_below_threshold() -> None:
    obj = ConcreteTrailing(TS_CONFIG, initial_pnl_pct=Decimal("0.01"))  # below 0.02
    obj.update_trailing_stop(Decimal("101"))
    assert obj.trailing_stop_activated is False


def test_activates_at_threshold() -> None:
    obj = ConcreteTrailing(TS_CONFIG, initial_pnl_pct=Decimal("0.02"))  # exactly 0.02
    obj.update_trailing_stop(Decimal("102"))
    assert obj.trailing_stop_activated is True


def test_not_triggered_immediately_after_activation() -> None:
    obj = ConcreteTrailing(TS_CONFIG, initial_pnl_pct=Decimal("0.03"))
    obj.update_trailing_stop(Decimal("103"))
    assert obj.trailing_stop_activated is True
    assert obj.trailing_stop_triggered is False


def test_ratchet_advances_trigger_on_higher_pnl() -> None:
    obj = ConcreteTrailing(TS_CONFIG, initial_pnl_pct=Decimal("0.02"))
    obj.update_trailing_stop(Decimal("102"))  # activates; trigger at 0.01
    obj._pnl_pct = Decimal("0.04")
    obj.update_trailing_stop(Decimal("104"))  # ratchet; trigger at 0.03
    # PnL drops to 0.025 — above trigger (0.03), not triggered
    obj._pnl_pct = Decimal("0.031")  # above trigger (0.03), not triggered
    obj.update_trailing_stop(Decimal("103.1"))
    assert obj.trailing_stop_triggered is False
    # PnL drops below trigger
    obj._pnl_pct = Decimal("0.02")
    obj.update_trailing_stop(Decimal("102"))
    assert obj.trailing_stop_triggered is True


def test_triggered_when_pnl_drops_below_trigger() -> None:
    obj = ConcreteTrailing(TS_CONFIG, initial_pnl_pct=Decimal("0.02"))
    obj.update_trailing_stop(Decimal("102"))  # activates; trigger=0.01
    obj._pnl_pct = Decimal("0.005")  # below trigger
    obj.update_trailing_stop(Decimal("100.5"))
    assert obj.trailing_stop_triggered is True


def test_init_trailing_stop_resets_state() -> None:
    obj = ConcreteTrailing(TS_CONFIG, initial_pnl_pct=Decimal("0.05"))
    obj.update_trailing_stop(Decimal("105"))
    obj._init_trailing_stop()
    assert obj.trailing_stop_activated is False
    assert obj.trailing_stop_triggered is False
```

- [ ] **Step 10.2: Run to verify failure**

```bash
pixi run test tests/unit/mixins/executor/test_trailing_stop.py -v
```

- [ ] **Step 10.3: Write `TrailingStopMixin`**

`strategy_framework/mixins/executor/trailing_stop.py`:

```python
"""TrailingStopMixin — PnL-based trailing stop ratchet algorithm.

Ported from hummingbot/strategy_v2/executors/mixins/trailing_stop.py.
Key adaptation: uses TrailingStop.activation_price_pct and trailing_delta_pct
(with _pct suffix) — NOT the in-tree names activation_price/trailing_delta.

Tracks PnL-percentage-based trigger (not price), reading net_pnl_pct from
BarrierControlProtocol.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from strategy_framework.protocols.composites import BarrierControlProtocol


class TrailingStopMixin:
    """Mixin providing the trailing stop ratchet algorithm.

    Algorithm:
    1. Wait until net_pnl_pct >= trailing_stop.activation_price_pct
    2. Set trigger = net_pnl_pct - trailing_delta_pct
    3. Ratchet trigger upward as PnL rises (trigger = max(trigger, pnl - delta))
    4. trailing_stop_triggered = True when pnl drops below trigger

    Usage:
        class MyExecutor(TrailingStopMixin):
            def __init__(self) -> None:
                self._init_trailing_stop()

            # host must provide via BarrierControlProtocol:
            #   net_pnl_pct: Decimal (property)
            #   trailing_stop: TrailingStop | None (property)
            #   status, close_type, triple_barrier, elapsed_seconds, place_close_order

            def _check_trailing_stop(self) -> None:
                self.update_trailing_stop(self.market.get_mid_price())
                if self.trailing_stop_triggered:
                    self.place_close_order(CloseType.TRAILING_STOP)

    SIDE EFFECT: update_trailing_stop() may advance the trigger floor.
    Call only once per price tick — do not call speculatively.

    MRO init order: call _init_trailing_stop() after all super().__init__() calls.
    Calling _init_trailing_stop() twice resets state (safe in diamond MRO).
    """

    def _init_trailing_stop(self: BarrierControlProtocol) -> None:  # type: ignore[misc]
        """Initialize trailing stop state. Call from __init__ after super().__init__()."""
        self._trailing_stop_trigger_pct: Decimal | None = None  # type: ignore[attr-defined]
        self._trailing_stop_activated: bool = False  # type: ignore[attr-defined]
        self._trailing_stop_triggered: bool = False  # type: ignore[attr-defined]

    def update_trailing_stop(
        self: BarrierControlProtocol,  # type: ignore[misc]
        current_price: Decimal,  # noqa: ARG002 — reserved for price-based future variant
    ) -> None:
        """Advance the trailing stop ratchet based on current PnL.

        SIDE EFFECT: may set _trailing_stop_trigger_pct and _trailing_stop_triggered.
        Call once per price tick only.

        current_price is accepted but unused — the algorithm is PnL-pct-based.
        Provided for API consistency; a future subclass may use price-based ratchet.
        """
        ts = self.trailing_stop
        if ts is None:
            return

        pnl_pct = self.net_pnl_pct

        if not self._trailing_stop_activated:  # type: ignore[attr-defined]
            if pnl_pct >= ts.activation_price_pct:
                self._trailing_stop_activated = True  # type: ignore[attr-defined]
                self._trailing_stop_trigger_pct = pnl_pct - ts.trailing_delta_pct  # type: ignore[attr-defined]
            return

        # Already activated — check fire condition
        if pnl_pct < self._trailing_stop_trigger_pct:  # type: ignore[operator]
            self._trailing_stop_triggered = True  # type: ignore[attr-defined]
            return

        # Ratchet: advance trigger floor if PnL has risen
        new_trigger = pnl_pct - ts.trailing_delta_pct
        if new_trigger > self._trailing_stop_trigger_pct:  # type: ignore[operator]
            self._trailing_stop_trigger_pct = new_trigger  # type: ignore[attr-defined]

    @property
    def trailing_stop_triggered(self: BarrierControlProtocol) -> bool:  # type: ignore[misc]
        """True if the trailing stop condition has been met."""
        return self._trailing_stop_triggered  # type: ignore[attr-defined]

    @property
    def trailing_stop_activated(self: BarrierControlProtocol) -> bool:  # type: ignore[misc]
        """True if activation threshold has been crossed (ratchet is live)."""
        return self._trailing_stop_activated  # type: ignore[attr-defined]
```

- [ ] **Step 10.4: Run tests**

```bash
pixi run test tests/unit/mixins/executor/test_trailing_stop.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 10.5: Commit**

```bash
git add strategy_framework/mixins/executor/trailing_stop.py tests/unit/mixins/executor/test_trailing_stop.py
git commit -m "feat(mixins): add TrailingStopMixin with PnL-pct ratchet algorithm"
```

---

## Task 11: Integration Tests

**Files:**
- Create: `tests/integration/test_mixin_composition.py`

Verifies MRO-safe composition of multiple mixins, state isolation between mixins, and the key real-world combination: `PNLCalculatorMixin + TrailingStopMixin`.

- [ ] **Step 11.1: Write the integration tests**

`tests/integration/test_mixin_composition.py`:

```python
"""Integration tests for mixin composition.

Tests verify:
1. MRO-safe _init_*() call order
2. State isolation between mixins
3. PNLCalculatorMixin + TrailingStopMixin real-world composition
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from strategy_framework.mixins.executor import (
    OrderTrackingMixin,
    PNLCalculatorMixin,
    RetryMixin,
    TrailingStopMixin,
)
from strategy_framework.primitives.enums import CloseType, RunnableStatus, TradeType
from strategy_framework.primitives.trailing_stop import TrailingStop
from strategy_framework.primitives.triple_barrier import TripleBarrierConfig
from strategy_framework.testing.factories import TrackedOrderFactory


# ---------------------------------------------------------------------------
# Composite 1: Retry + OrderTracking + TrailingStop
# ---------------------------------------------------------------------------


class MultiMixinExecutor(RetryMixin, OrderTrackingMixin, TrailingStopMixin):
    """Combines three mixins — verifies MRO and state isolation."""

    max_retries: int = 3
    close_type: CloseType | None = None
    status = RunnableStatus.RUNNING
    elapsed_seconds: float = 0.0

    def __init__(self, pnl_pct: Decimal = Decimal("0")) -> None:
        self._pnl_pct = pnl_pct
        self._init_retry()
        self._init_order_tracking()
        self._init_trailing_stop()

    @property
    def net_pnl_pct(self) -> Decimal:
        return self._pnl_pct

    @property
    def trailing_stop(self) -> TrailingStop | None:
        return TrailingStop(
            activation_price_pct=Decimal("0.02"),
            trailing_delta_pct=Decimal("0.01"),
        )

    @property
    def triple_barrier(self) -> TripleBarrierConfig:
        return TripleBarrierConfig(stop_loss=Decimal("0.05"), take_profit=Decimal("0.1"))

    def place_close_order(self, close_type: CloseType) -> None:
        self.close_type = close_type


def test_all_mixins_initialize() -> None:
    obj = MultiMixinExecutor()
    assert obj.current_retries == 0
    assert obj.open_orders == []
    assert obj.trailing_stop_activated is False


def test_retry_state_independent_of_order_tracking() -> None:
    obj = MultiMixinExecutor()
    obj.increment_retries()
    obj.add_open_order(TrackedOrderFactory.open_order())
    assert obj.current_retries == 1
    assert len(obj.open_orders) == 1


def test_order_tracking_unaffected_by_retry_reset() -> None:
    obj = MultiMixinExecutor()
    obj.add_open_order(TrackedOrderFactory.open_order(order_id="o1"))
    obj.increment_retries()
    obj._init_retry()  # reset retry state only
    assert len(obj.open_orders) == 1  # order tracking unaffected
    assert obj.current_retries == 0


def test_double_init_resets_all_state() -> None:
    obj = MultiMixinExecutor()
    obj.increment_retries()
    obj.add_open_order(TrackedOrderFactory.open_order())
    obj._init_retry()
    obj._init_order_tracking()
    obj._init_trailing_stop()
    assert obj.current_retries == 0
    assert obj.open_orders == []
    assert obj.trailing_stop_activated is False


# ---------------------------------------------------------------------------
# Composite 2: PNLCalculatorMixin + TrailingStopMixin
# (trailing stop reads net_pnl_pct from PNLCalculatorMixin)
# ---------------------------------------------------------------------------


class PnLTrailingExecutor(PNLCalculatorMixin, TrailingStopMixin):
    """Key real-world composition: trailing stop fires when PnL drops enough."""

    close_type: CloseType | None = None
    status = RunnableStatus.RUNNING
    elapsed_seconds: float = 0.0

    def __init__(
        self,
        entry: str,
        close: str,
        filled_quote: str,
        side: TradeType = TradeType.BUY,
        fees: str = "0",
    ) -> None:
        self._entry = Decimal(entry)
        self._close = Decimal(close)
        self._filled_quote = Decimal(filled_quote)
        self._side = side
        self._fees = Decimal(fees)
        self._init_trailing_stop()

    @property
    def entry_price(self) -> Decimal:
        return self._entry

    @property
    def close_price(self) -> Decimal:
        return self._close

    @property
    def open_filled_amount_quote(self) -> Decimal:
        return self._filled_quote

    @property
    def trade_side(self) -> TradeType:
        return self._side

    @property
    def cum_fees_raw(self) -> Decimal:
        return self._fees

    @property
    def trailing_stop(self) -> TrailingStop | None:
        return TrailingStop(
            activation_price_pct=Decimal("0.05"),
            trailing_delta_pct=Decimal("0.02"),
        )

    @property
    def triple_barrier(self) -> TripleBarrierConfig:
        return TripleBarrierConfig(stop_loss=Decimal("0.1"), take_profit=Decimal("0.2"))

    def place_close_order(self, close_type: CloseType) -> None:
        self.close_type = close_type


def test_pnl_trailing_stop_activates_at_threshold() -> None:
    # BUY at 100, close=105 → pnl_pct=0.05 (at activation threshold)
    obj = PnLTrailingExecutor("100", "105", "1000")
    obj.update_trailing_stop(Decimal("105"))
    assert obj.trailing_stop_activated is True


def test_pnl_trailing_stop_not_triggered_at_activation() -> None:
    obj = PnLTrailingExecutor("100", "105", "1000")
    obj.update_trailing_stop(Decimal("105"))
    assert obj.trailing_stop_triggered is False


def test_pnl_trailing_stop_triggered_after_reversal() -> None:
    # Activates at +5%, rises to +8%, then reverses to +5.5% (below trigger of 6%)
    obj = PnLTrailingExecutor("100", "108", "1000")  # pnl=+8%
    obj.update_trailing_stop(Decimal("108"))          # activates; trigger=6%
    obj._close = Decimal("105.5")                     # pnl drops to ~5.5%
    obj.update_trailing_stop(Decimal("105.5"))        # 5.5% < 6% trigger → fires
    assert obj.trailing_stop_triggered is True
```

- [ ] **Step 11.2: Run integration tests**

```bash
pixi run test tests/integration/test_mixin_composition.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 11.3: Commit**

```bash
git add tests/integration/test_mixin_composition.py
git commit -m "test(integration): add mixin composition tests"
```

---

## Task 12: Public API Exports + Final Quality Gate

**Files:**
- Modify: `strategy_framework/__init__.py`
- Run: full quality suite

Expose the new mixin layer through the top-level public API.

- [ ] **Step 12.1: Add mixin exports to `__init__.py`**

Add to `strategy_framework/__init__.py`:

```python
# Mixins
from strategy_framework.mixins.executor import (
    ActivationBoundsMixin,
    BalanceValidationMixin,
    OrderTrackingMixin,
    PNLCalculatorMixin,
    RetryMixin,
    ShutdownMixin,
    TrailingStopMixin,
)
```

Also add the new protocol names to imports and `__all__`:

```python
from strategy_framework.protocols.composites import (
    ActivationBoundsProtocol,
    BarrierControlProtocol,
    OrderTrackingProtocol,
    PnLHostProtocol,
    PnLProtocol,
    RetryHostProtocol,
    RetryProtocol,
)
```

And add all new names to `__all__`.

- [ ] **Step 12.2: Run the full test suite**

```bash
pixi run test -v
```

Expected: all tests PASS (≥80 total, ≥90% coverage target).

- [ ] **Step 12.3: Run typecheck**

```bash
pixi run typecheck
```

Expected: no errors.

- [ ] **Step 12.4: Run lint and format check**

```bash
pixi run lint
pixi run format-check
```

Expected: clean.

- [ ] **Step 12.5: Final commit**

```bash
git add strategy_framework/__init__.py
git commit -m "feat(api): expose mixin layer in public API"
```

- [ ] **Step 12.6: Push branch**

```bash
git push origin development
```

---

## Checklist Summary

| Task | Description | Tests |
|------|-------------|-------|
| 1 | Protocol amendments (market.py + composites.py) | mypy clean |
| 2 | TrackedOrderFactory | 3 tests |
| 3 | Module scaffolding | collection clean |
| 4 | RetryMixin | 9 tests |
| 5 | ShutdownMixin | 6 tests |
| 6 | ActivationBoundsMixin | 7 tests |
| 7 | BalanceValidationMixin (stub) | 3 tests |
| 8 | OrderTrackingMixin | 10 tests |
| 9 | PNLCalculatorMixin | 10 tests |
| 10 | TrailingStopMixin | 9 tests |
| 11 | Integration tests | 9 tests |
| 12 | Public API + quality gate | all pass |

**Total:** ~66 unit + 9 integration = ~75 tests. Coverage ≥90%, mypy strict, ruff clean.
