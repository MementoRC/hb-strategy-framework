"""LoggerAdapter — canonical logger factory delegating to hb-logger's HummingbotLogger."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

import logger  # noqa: F401 -- side effect: registers HummingbotLogger via logging.setLoggerClass

if TYPE_CHECKING:
    from logger import HummingbotLogger

__all__ = ["get_logger"]


def get_logger(name: str) -> HummingbotLogger:
    """Return a :class:`HummingbotLogger` instance for ``name``.

    Importing the ``logger`` sub-package (hb-logger) registers
    ``HummingbotLogger`` as the process-wide logging class via
    ``logging.setLoggerClass``, so ``logging.getLogger`` returns
    ``HummingbotLogger`` instances for every logger created after that
    import — including this one.
    """
    return cast("HummingbotLogger", logging.getLogger(name))
