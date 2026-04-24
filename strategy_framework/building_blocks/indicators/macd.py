"""MACD indicator."""

from __future__ import annotations

import pandas as pd  # noqa: TC002 — runtime usage (df.copy(), pd.Series)
import pandas_ta as ta  # type: ignore[import-untyped]


def macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """Add MACD columns to a copy of df.

    Args:
        df: DataFrame with OHLCV columns (open, high, low, close, volume).
        fast: Fast EMA period. Default 12.
        slow: Slow EMA period. Default 26.
        signal: Signal EMA period. Default 9.

    Returns:
        New DataFrame with original columns plus:
            macd:        MACD line (fast EMA - slow EMA).
            macd_signal: Signal line (EMA of MACD).
            macd_hist:   Histogram (macd - macd_signal).
    """
    result = df.copy()
    macd_df = ta.macd(result["close"], fast=fast, slow=slow, signal=signal)
    if macd_df is None or macd_df.empty:
        result["macd"] = float("nan")
        result["macd_signal"] = float("nan")
        result["macd_hist"] = float("nan")
        return result

    # pandas_ta columns: MACD_F_S_SIG, MACDh_F_S_SIG, MACDs_F_S_SIG
    prefix = f"_{fast}_{slow}_{signal}"
    result["macd"] = macd_df.get(f"MACD{prefix}")
    result["macd_hist"] = macd_df.get(f"MACDh{prefix}")
    result["macd_signal"] = macd_df.get(f"MACDs{prefix}")
    return result
