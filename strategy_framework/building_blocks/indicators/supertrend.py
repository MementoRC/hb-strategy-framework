"""Supertrend indicator — stub (to be implemented)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


def supertrend(
    df: pd.DataFrame,
    length: int = 7,
    multiplier: float = 3.0,
) -> pd.DataFrame:
    """Add Supertrend columns to a copy of df (stub)."""
    raise NotImplementedError("supertrend is not yet implemented")
