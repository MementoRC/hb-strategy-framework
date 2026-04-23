"""RSI indicator — stub (to be implemented)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


def rsi(
    df: pd.DataFrame,
    length: int = 14,
) -> pd.DataFrame:
    """Add RSI column to a copy of df (stub)."""
    raise NotImplementedError("rsi is not yet implemented")
