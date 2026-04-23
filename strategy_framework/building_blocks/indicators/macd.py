"""MACD indicator — stub (to be implemented)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


def macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """Add MACD columns to a copy of df (stub)."""
    raise NotImplementedError("macd is not yet implemented")
