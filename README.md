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

# Option 3: pip
pip install -e ".[dev]"
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

## License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.
