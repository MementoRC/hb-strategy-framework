"""Tests for bollinger_bands indicator function."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from strategy_framework.building_blocks.indicators.bollinger import bollinger_bands

EXPECTED_COLUMNS = {"bb_upper", "bb_lower", "bb_mid", "bbp"}


def make_ohlcv(n: int = 100) -> pd.DataFrame:
    close = 100.0 + np.cumsum(np.random.default_rng(42).normal(0, 1, n))
    return pd.DataFrame({
        "open": close - 0.5, "high": close + 1.0,
        "low": close - 1.0, "close": close, "volume": np.ones(n) * 1000.0,
    })


def test_returns_dataframe_with_expected_columns():
    df = make_ohlcv()
    result = bollinger_bands(df)
    assert EXPECTED_COLUMNS.issubset(result.columns)


def test_does_not_mutate_input():
    df = make_ohlcv()
    original_columns = set(df.columns)
    bollinger_bands(df)
    assert set(df.columns) == original_columns


def test_output_is_new_dataframe():
    df = make_ohlcv()
    result = bollinger_bands(df)
    assert result is not df


def test_sufficient_rows_produces_non_nan_values():
    df = make_ohlcv(100)
    result = bollinger_bands(df, length=20)
    # Rows after the window should have valid values
    tail = result.tail(50)
    assert not tail["bb_upper"].isna().all()
    assert not tail["bb_lower"].isna().all()
    assert not tail["bb_mid"].isna().all()


def test_upper_greater_than_lower():
    df = make_ohlcv(100)
    result = bollinger_bands(df, length=20)
    valid = result.dropna(subset=["bb_upper", "bb_lower"])
    assert (valid["bb_upper"] >= valid["bb_lower"]).all()


def test_insufficient_rows_produces_nan():
    df = make_ohlcv(n=5)
    result = bollinger_bands(df, length=20)
    assert result["bb_upper"].isna().all()


def test_empty_dataframe_returns_nan_columns():
    df = make_ohlcv(n=0)
    result = bollinger_bands(df)
    assert EXPECTED_COLUMNS.issubset(result.columns)
    assert len(result) == 0


def test_custom_parameters_accepted():
    df = make_ohlcv(100)
    result = bollinger_bands(df, length=10, std=1.5)
    assert EXPECTED_COLUMNS.issubset(result.columns)


def test_flat_price_series_bands_collapse():
    """When all close prices are identical, std=0 so bands equal mid."""
    df = pd.DataFrame({
        "open": [100.0] * 30, "high": [100.0] * 30,
        "low": [100.0] * 30, "close": [100.0] * 30,
        "volume": [1000.0] * 30,
    })
    result = bollinger_bands(df, length=20, std=2.0)
    valid = result.dropna(subset=["bb_upper", "bb_lower", "bb_mid"])
    assert not valid.empty
    # All prices identical → std=0 → upper == lower == mid
    pd.testing.assert_series_equal(
        valid["bb_upper"].round(6), valid["bb_mid"].round(6), check_names=False
    )
    pd.testing.assert_series_equal(
        valid["bb_lower"].round(6), valid["bb_mid"].round(6), check_names=False
    )
