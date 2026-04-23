"""Bollinger Bands indicator."""

from __future__ import annotations

import pandas as pd
import pandas_ta as ta  # type: ignore[import-untyped]


def bollinger_bands(
    df: pd.DataFrame,
    length: int = 20,
    std: float = 2.0,
) -> pd.DataFrame:
    """Add Bollinger Band columns to a copy of df.

    Args:
        df: DataFrame with OHLCV columns (open, high, low, close, volume).
        length: Rolling window size. Default 20.
        std: Number of standard deviations. Default 2.0.

    Returns:
        New DataFrame with original columns plus:
            bb_upper: Upper band.
            bb_lower: Lower band.
            bb_mid:   Middle band (simple moving average).
            bbp:      Bandwidth percent — position of close within bands
                      (0 = at lower band, 1 = at upper band).
    """
    result = df.copy()
    bbands = ta.bbands(result["close"], length=length, std=std)
    if bbands is None or bbands.empty:
        result["bb_upper"] = float("nan")
        result["bb_lower"] = float("nan")
        result["bb_mid"] = float("nan")
        result["bbp"] = float("nan")
        return result

    # pandas_ta column naming: BBL_N_S, BBM_N_S, BBU_N_S, BBP_N_S
    # Use prefix-based lookup to avoid fragile float formatting (e.g. std=1.25).
    def _get_col(prefix: str) -> pd.Series:
        matches = [c for c in bbands.columns if c.startswith(prefix)]
        return bbands[matches[0]] if matches else pd.Series(float("nan"), index=result.index)

    result["bb_lower"] = _get_col("BBL_")
    result["bb_mid"] = _get_col("BBM_")
    result["bb_upper"] = _get_col("BBU_")
    result["bbp"] = _get_col("BBP_")
    return result
