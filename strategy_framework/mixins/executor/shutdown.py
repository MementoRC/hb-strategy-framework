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
