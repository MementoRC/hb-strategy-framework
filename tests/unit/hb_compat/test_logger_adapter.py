"""Tests for the logger_adapter hb_compat shim."""

from __future__ import annotations

import logging

from logger import HummingbotLogger

from strategy_framework.hb_compat.logger_adapter import get_logger


def test_get_logger_returns_hummingbot_logger():
    logger = get_logger(__name__)
    assert isinstance(logger, HummingbotLogger)


def test_get_logger_registers_as_process_wide_logger_class():
    # Importing the adapter (hence hb-logger) must register HummingbotLogger
    # as the process-wide logging class, so plain logging.getLogger also
    # returns HummingbotLogger instances.
    assert logging.getLoggerClass() is HummingbotLogger


def test_get_logger_returns_same_instance_for_same_name():
    first = get_logger("strategy_framework.hb_compat.test_logger_adapter")
    second = get_logger("strategy_framework.hb_compat.test_logger_adapter")
    assert first is second


def test_get_logger_supports_standard_logging_api(caplog):
    logger = get_logger("strategy_framework.hb_compat.test_logger_adapter.standard")
    with caplog.at_level(logging.WARNING, logger=logger.name):
        logger.warning("Order %s failed: %s", "o1", "timeout")
    assert "Order o1 failed: timeout" in caplog.text
