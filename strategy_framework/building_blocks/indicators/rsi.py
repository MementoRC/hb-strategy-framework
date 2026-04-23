"""RSI indicator."""

from __future__ import annotations

import pandas as pd  # noqa: TC002
import pandas_ta as ta  # type: ignore[import-untyped]


def rsi(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    """Add RSI column to a copy of df.

    Args:
        df: DataFrame with OHLCV columns (open, high, low, close, volume).
        length: RSI period. Default 14.

    Returns:
        New DataFrame with original columns plus:
            rsi: Relative Strength Index (0–100).
    """
    result = df.copy()
    rsi_series = ta.rsi(result["close"], length=length)
    result["rsi"] = rsi_series if rsi_series is not None else float("nan")
    return result
