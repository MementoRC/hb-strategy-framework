"""Tests for macd indicator function."""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategy_framework.building_blocks.indicators.macd import macd

EXPECTED_COLUMNS = {"macd", "macd_signal", "macd_hist"}


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
    result = macd(make_ohlcv())
    assert EXPECTED_COLUMNS.issubset(result.columns)


def test_does_not_mutate_input():
    df = make_ohlcv()
    original_columns = set(df.columns)
    macd(df)
    assert set(df.columns) == original_columns


def test_output_is_new_dataframe():
    df = make_ohlcv()
    assert macd(df) is not df


def test_sufficient_rows_produces_non_nan_values():
    result = macd(make_ohlcv(100), fast=12, slow=26, signal=9)
    tail = result.tail(20)
    assert not tail["macd"].isna().all()
    assert not tail["macd_signal"].isna().all()


def test_macd_hist_equals_macd_minus_signal():
    result = macd(make_ohlcv(100))
    valid = result.dropna(subset=["macd", "macd_signal", "macd_hist"])
    expected_hist = valid["macd"] - valid["macd_signal"]
    pd.testing.assert_series_equal(
        valid["macd_hist"].round(8), expected_hist.round(8), check_names=False
    )


def test_insufficient_rows_produces_nan():
    result = macd(make_ohlcv(n=5))
    assert result["macd"].isna().all()


def test_empty_dataframe_returns_nan_columns():
    result = macd(make_ohlcv(n=0))
    assert EXPECTED_COLUMNS.issubset(result.columns)
    assert len(result) == 0


def test_custom_parameters_accepted():
    result = macd(make_ohlcv(100), fast=5, slow=10, signal=3)
    assert EXPECTED_COLUMNS.issubset(result.columns)


def test_monotonic_uptrend_produces_positive_macd():
    """A steadily rising price gives fast EMA > slow EMA → positive MACD."""
    close = [float(i) for i in range(1, 101)]
    df = pd.DataFrame(
        {
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": [1000.0] * 100,
        }
    )
    result = macd(df)
    valid = result["macd"].dropna()
    assert not valid.empty
    assert (valid > 0).all()
