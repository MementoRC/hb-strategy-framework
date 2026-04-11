"""Global test fixtures and configuration for the strategy framework test suite.

Provides CI-aware fixtures, logging configuration, and common test
utilities following the patterns established in hb-candles-feed.
"""

from __future__ import annotations

import logging
import os

import pytest

# ─── CI Environment Detection ─────────────────────────────────────────────────

IS_CI = os.environ.get("CI", "false").lower() == "true"
CI_TIMEOUT_MULTIPLIER = 3 if IS_CI else 1
CI_RETRY_ATTEMPTS = 3 if IS_CI else 1


# ─── Logging Configuration ────────────────────────────────────────────────────


@pytest.fixture(scope="session", autouse=True)
def configure_logging():
    """Configure logging for the test session."""
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    # Reduce noise from third-party libraries
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
