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

    def _init_retry(self: RetryHostProtocol) -> None:
        """Initialize retry state. Call from __init__ after super().__init__()."""
        self.current_retries: int = 0  # type: ignore[attr-defined]

    def increment_retries(self: RetryHostProtocol) -> None:
        """Increment the retry counter by one."""
        self.current_retries += 1  # type: ignore[attr-defined]

    def has_exceeded_max_retries(self: RetryHostProtocol) -> bool:
        """Return True when current_retries >= max_retries.

        Note: uses >= (fires at exactly max_retries).
        """
        return bool(self.current_retries >= self.max_retries)  # type: ignore[attr-defined]
