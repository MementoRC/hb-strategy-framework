"""SuperTrend indicator."""

from __future__ import annotations

import pandas as pd  # noqa: TC002
import pandas_ta as ta  # type: ignore[import-untyped]


def supertrend(
    df: pd.DataFrame,
    length: int = 7,
    multiplier: float = 3.0,
) -> pd.DataFrame:
    """Add SuperTrend columns to a copy of df.

    Args:
        df: DataFrame with OHLCV columns (open, high, low, close, volume).
        length: ATR period. Default 7.
        multiplier: ATR multiplier. Default 3.0.

    Returns:
        New DataFrame with original columns plus:
            supertrend:           SuperTrend line value.
            supertrend_direction: Trend direction: +1 (uptrend) or -1 (downtrend).
    """
    result = df.copy()
    st = ta.supertrend(
        result["high"], result["low"], result["close"], length=length, multiplier=multiplier
    )
    if st is None or st.empty:
        result["supertrend"] = float("nan")
        result["supertrend_direction"] = float("nan")
        return result

    # pandas_ta columns: SUPERT_L_M, SUPERTd_L_M, SUPERTl_L_M, SUPERTs_L_M
    prefix = f"_{length}_{multiplier:.1f}"
    result["supertrend"] = st.get(f"SUPERT{prefix}")
    direction_raw = st.get(f"SUPERTd{prefix}")
    # pandas_ta returns 1 (up) / -1 (down) already
    result["supertrend_direction"] = direction_raw
    return result
