"""
Tests for dags/src/performance_test/performance_test.py.

Covers: add_noise_to_features
This function is used by the performance_test_dag.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pandas as pd
import pytest

from src.performance_test.performance_test import add_noise_to_features


class TestAddNoiseToFeatures:
    @pytest.fixture
    def sample_X(self):
        np.random.seed(42)
        return pd.DataFrame(
            {
                "temp_fr": np.random.uniform(-5, 35, 100),
                "snow_fr": np.random.uniform(0, 10, 100),
                "hour": np.random.randint(0, 24, 100),
                "month": np.random.randint(1, 13, 100),
            }
        )

    def test_add_noise_returns_dataframe(self, sample_X):
        result = add_noise_to_features(sample_X, 0.1)
        assert isinstance(result, pd.DataFrame)

    def test_add_noise_same_shape(self, sample_X):
        result = add_noise_to_features(sample_X, 0.1)
        assert result.shape == sample_X.shape

    def test_add_noise_zero_noise_returns_copy(self, sample_X):
        result = add_noise_to_features(sample_X, 0.0)
        # Should be identical (noise_level=0 → no noise added)
        # Numeric columns may become float after noise injection; compare content not dtype
        for col in sample_X.columns:
            pd.testing.assert_series_equal(
                result[col].astype(sample_X[col].dtype) if pd.api.types.is_numeric_dtype(result[col]) else result[col],
                sample_X[col],
                check_dtype=False,
            )

    def test_add_noise_preserves_column_names(self, sample_X):
        result = add_noise_to_features(sample_X, 0.1)
        assert list(result.columns) == list(sample_X.columns)

    def test_add_noise_changes_values(self, sample_X):
        result = add_noise_to_features(sample_X, 0.5)
        # With 0.5 std noise, values should differ
        assert not np.allclose(result.values, sample_X.values)

    def test_add_noise_deterministic_with_seed(self, sample_X):
        r1 = add_noise_to_features(sample_X, 0.2, seed=123)
        r2 = add_noise_to_features(sample_X, 0.2, seed=123)
        pd.testing.assert_frame_equal(r1, r2)

    def test_add_noise_different_seed_different_result(self, sample_X):
        r1 = add_noise_to_features(sample_X, 0.2, seed=1)
        r2 = add_noise_to_features(sample_X, 0.2, seed=2)
        assert not np.allclose(r1.values, r2.values)

    def test_add_noise_non_numeric_columns_unchanged(self):
        X = pd.DataFrame(
            {
                "temp": [10.0, 20.0, 30.0],
                "city": ["Paris", "Lyon", "Marseille"],
                "code": [1, 2, 3],
            }
        )
        result = add_noise_to_features(X, 0.1)
        # String column should be identical
        assert list(result["city"]) == list(X["city"])

    def test_add_noise_higher_noise_more_deviation(self, sample_X):
        low_noise = add_noise_to_features(sample_X, 0.01)
        high_noise = add_noise_to_features(sample_X, 0.5, seed=1)
        low_diff = np.abs(low_noise - sample_X).mean().mean()
        high_diff = np.abs(high_noise - sample_X).mean().mean()
        assert high_diff > low_diff

    def test_add_noise_single_row(self):
        X = pd.DataFrame({"a": [10.0], "b": [20.0]})
        result = add_noise_to_features(X, 0.1)
        assert len(result) == 1
        assert list(result.columns) == ["a", "b"]

    def test_add_noise_zero_std_column(self):
        X = pd.DataFrame({"constant": [5.0, 5.0, 5.0], "varying": [1.0, 2.0, 3.0]})
        result = add_noise_to_features(X, 0.1)
        # Constant column should remain unchanged (std=0 ⇒ skip)
        assert list(result["constant"]) == [5.0, 5.0, 5.0]
