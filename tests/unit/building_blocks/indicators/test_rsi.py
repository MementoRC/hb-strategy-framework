"""Tests for rsi indicator function."""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategy_framework.building_blocks.indicators.rsi import rsi

EXPECTED_COLUMNS = {"rsi"}


def make_ohlcv(n: int = 100) -> pd.DataFrame:
    close = 100.0 + np.cumsum(np.random.default_rng(42).normal(0, 1, n))
    return pd.DataFrame({
        "open": close - 0.5, "high": close + 1.0,
        "low": close - 1.0, "close": close, "volume": np.ones(n) * 1000.0,
    })


def test_returns_dataframe_with_expected_columns():
    result = rsi(make_ohlcv())
    assert EXPECTED_COLUMNS.issubset(result.columns)


def test_does_not_mutate_input():
    df = make_ohlcv()
    original_columns = set(df.columns)
    rsi(df)
    assert set(df.columns) == original_columns


def test_output_is_new_dataframe():
    df = make_ohlcv()
    assert rsi(df) is not df


def test_rsi_bounded_between_0_and_100():
    result = rsi(make_ohlcv(100))
    valid = result["rsi"].dropna()
    assert (valid >= 0).all()
    assert (valid <= 100).all()


def test_insufficient_rows_produces_nan():
    result = rsi(make_ohlcv(n=3))
    assert result["rsi"].isna().all()


def test_empty_dataframe_returns_nan_columns():
    result = rsi(make_ohlcv(n=0))
    assert EXPECTED_COLUMNS.issubset(result.columns)
    assert len(result) == 0


def test_custom_length_accepted():
    result = rsi(make_ohlcv(100), length=7)
    assert EXPECTED_COLUMNS.issubset(result.columns)


def test_all_gains_series_produces_high_rsi():
    """A monotonically rising price has all gains, no losses → RSI near 100."""
    close = [float(100 + i) for i in range(50)]
    df = pd.DataFrame({
        "open": close, "high": close, "low": close,
        "close": close, "volume": [1000.0] * 50,
    })
    result = rsi(df, length=14)
    valid = result["rsi"].dropna()
    assert not valid.empty
    assert (valid > 90).all()
