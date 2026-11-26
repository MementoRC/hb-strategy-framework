# hb-strategy-framework

[![CI](https://github.com/MementoRC/hb-strategy-framework/actions/workflows/ci.yml/badge.svg)](https://github.com/MementoRC/hb-strategy-framework/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/MementoRC/hb-strategy-framework)](https://codecov.io/gh/MementoRC/hb-strategy-framework)
[![PyPI version](https://badge.fury.io/py/hb-strategy-framework.svg)](https://badge.fury.io/py/hb-strategy-framework)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

A modular strategy framework for Hummingbot trading strategies, built as a standalone sub-package following Hexagonal Architecture principles.

## Overview

This package provides a framework for building, testing, and running trading strategies within the Hummingbot ecosystem. It operates both as a standalone library and as a drop-in replacement for Hummingbot's built-in strategy modules via the `hb_compat` compatibility layer.

## Features

- **Hexagonal Architecture**: Clean separation between core domain logic, adapters, and external integrations
- **Protocol-Based Design**: Runtime-checkable protocols define all interfaces for maximum flexibility
- **Hummingbot Compatibility**: `hb_compat` layer provides seamless integration with Hummingbot's strategy orchestration
- **Standalone Capability**: Works independently of Hummingbot for testing and development
- **Async-First**: Built on asyncio for efficient I/O-bound operations
- **Cython Support**: Decorator-based Cython compilation for performance-critical code

## Installation

```bash
# Clone the repository
git clone https://github.com/MementoRC/hb-strategy-framework.git
cd strategy-framework

# Option 1: Pixi (recommended)
pixi install
pixi run test

# Option 2: Conda + Hatch
./setup-dev-env.sh
```

## Project Structure

```
strategy-framework/
├── strategy_framework/          # Package source
│   ├── __init__.py              # Package exports
│   ├── __about__.py             # Version: "0.1.0"
│   ├── core/                    # Domain layer
│   │   ├── __init__.py
│   │   └── protocols.py         # Core protocol interfaces
│   ├── adapters/                # Adapter layer
│   │   ├── __init__.py
│   │   └── protocols.py         # Adapter protocol interfaces
│   └── hb_compat/               # Hummingbot compatibility layer
│       ├── __init__.py
│       ├── data_types.py        # Pydantic config models
│       └── protocols.py         # HB-compatible protocol
├── tests/                       # Test suite
│   ├── conftest.py              # CI-aware global fixtures
│   ├── unit/                    # Unit tests
│   ├── integration/             # Integration tests
│   └── e2e/                     # End-to-end tests
├── docs/                        # MkDocs documentation
├── setup-tools/                 # Build utilities
├── .github/                     # CI/CD workflows
├── pyproject.toml               # Primary configuration
└── .pre-commit-config.yaml      # Pre-commit hooks
```

## Running Tests

```bash
# Pixi (recommended)
pixi run test               # All tests
pixi run test-unit           # Unit tests only
pixi run test-integration    # Integration tests only
pixi run lint                # Lint check
pixi run typecheck           # Type check
pixi run check               # Full quality + test suite

# Hatch
hatch run test
hatch run test -- --cov=strategy_framework

# pytest directly
pytest tests/
pytest tests/unit/ --cov=strategy_framework
```

## Architecture

This package follows the **Hexagonal Architecture** (Ports & Adapters) pattern:

- **Core** (`strategy_framework/core/`): Business logic and domain protocols, independent of external systems
- **Adapters** (`strategy_framework/adapters/`): Bridge between core domain and external systems
- **hb_compat** (`strategy_framework/hb_compat/`): Integration layer for Hummingbot compatibility

## Emulated linked orders: hazards

`strategy_framework.linked_orders` (opt-in; not re-exported from the top-level package) emulates
OCO and BRACKET on venues without native support. Each leg is the venue's own native order; the
manager emulates only the *link* (when one leg fills, it cancels the siblings). Read this before
enabling `LinkedOrderManagerConfig(enabled=True)`:

- **Double fill.** Emulated OCO cannot give native OCA guarantees. A sibling can fill before its
  cancel lands, while the process is down or the stream is lost, while a cancel is deferred on an
  unresolved leg, or as a late CANCELED-with-fill report. The manager detects this (the group goes
  DEGRADED with `DOUBLE_FILL`, with an event and a WARNING log) but never prevents it and never
  places compensating orders.
- **Unprotected entry window (BRACKET).** Exits are placed once, only after the entry is terminal
  and its final fill is confirmed, sized `min(exit.amount, filled)`. A partially filled entry has no
  protection until then. Limit the window with the entry order type and `cancel_linked` (which never
  places exits).
- **Unprotected after an exit rejection.** A rejected exit (for example below the venue minimum
  after resizing) is not retried: the group goes DEGRADED (`EXIT_PLACEMENT_FAILED`), the remaining
  exits are still placed, and the position is unprotected or only partially protected.
- **Durable store required.** The write-ahead record is what lets `recover()` find legs after a
  crash. A non-durable store is refused unless `allow_volatile_store` is set (tests only).
- **Volatile group ids.** Without `allocator=` or a store implementing `GroupIdHighWaterStore`
  with a durable mark, group ids (and so link tags) can repeat after a restart, and IB silently
  drops fills for a reused tag. `InMemoryLinkedGroupStore` counts as volatile
  (`group_id_hwm_durable = False`; custom stores may set it too, default True). Volatile ids
  currently log a WARNING; a future release will make this an error. Pass `allocator=`, use a
  store with a durable high-water mark, or set `allow_volatile_group_ids=True` (backtests, tests,
  single-shot runs).
- **Callers drive it.** The manager starts no tasks: feed `on_order_update` / `on_fill` and call
  `tick()` periodically. `place_*` returns once submission is done; check `handle.state` and
  subscribe to `"linked.group"` events. `shutdown()` persists and reports; it never cancels.

## License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.
