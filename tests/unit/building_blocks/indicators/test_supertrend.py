"""Tests for supertrend indicator function."""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategy_framework.building_blocks.indicators.supertrend import supertrend

EXPECTED_COLUMNS = {"supertrend", "supertrend_direction"}


def make_ohlcv(n: int = 100) -> pd.DataFrame:
    close = 100.0 + np.cumsum(np.random.default_rng(42).normal(0, 1, n))
    return pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": np.ones(n) * 1000.0,
        }
    )


def test_returns_dataframe_with_expected_columns():
    result = supertrend(make_ohlcv())
    assert EXPECTED_COLUMNS.issubset(result.columns)


def test_does_not_mutate_input():
    df = make_ohlcv()
    original_columns = set(df.columns)
    supertrend(df)
    assert set(df.columns) == original_columns


def test_output_is_new_dataframe():
    df = make_ohlcv()
    assert supertrend(df) is not df


def test_sufficient_rows_produces_non_nan_values():
    result = supertrend(make_ohlcv(100), length=7)
    tail = result.tail(50)
    assert not tail["supertrend"].isna().all()
    assert not tail["supertrend_direction"].isna().all()


def test_direction_is_binary():
    """supertrend_direction must be +1 (uptrend) or -1 (downtrend)."""
    result = supertrend(make_ohlcv(100))
    valid = result["supertrend_direction"].dropna()
    assert set(valid.unique()).issubset({1.0, -1.0})


def test_insufficient_rows_produces_nan():
    result = supertrend(make_ohlcv(n=3))
    assert result["supertrend"].isna().all()


def test_empty_dataframe_returns_nan_columns():
    result = supertrend(make_ohlcv(n=0))
    assert EXPECTED_COLUMNS.issubset(result.columns)
    assert len(result) == 0


def test_custom_parameters_accepted():
    result = supertrend(make_ohlcv(100), length=14, multiplier=2.0)
    assert EXPECTED_COLUMNS.issubset(result.columns)


def test_sustained_uptrend_direction_is_positive():
    """A strongly trending upward price should yield direction=1 in the tail."""
    close = [float(100 + i * 2) for i in range(100)]  # strong uptrend
    df = pd.DataFrame(
        {
            "open": [c - 0.1 for c in close],
            "high": [c + 0.5 for c in close],
            "low": [c - 0.5 for c in close],
            "close": close,
            "volume": [1000.0] * 100,
        }
    )
    result = supertrend(df, length=7)
    tail_direction = result["supertrend_direction"].dropna().tail(10)
    assert not tail_direction.empty
    assert (tail_direction == 1).all()
