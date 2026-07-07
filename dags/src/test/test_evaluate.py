"""
Tests for dags/src/modeling/evaluate.py.

Covers: mape, evaluate_model
Used by the training_dag and performance_test_dag.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pytest
from sklearn.linear_model import LinearRegression

from src.modeling.evaluate import mape, evaluate_model


class TestMape:
    def test_mape_perfect_prediction(self):
        y_true = np.array([100, 200, 300])
        y_pred = np.array([100, 200, 300])
        assert mape(y_true, y_pred) == pytest.approx(0.0)

    def test_mape_off_by_constant_factor(self):
        y_true = np.array([100, 200, 300])
        y_pred = np.array([110, 220, 330])
        # MAPE = mean(|(100-110)/100|, |(200-220)/200|, |(300-330)/300|) * 100
        expected = np.mean([0.1, 0.1, 0.1]) * 100
        assert mape(y_true, y_pred) == pytest.approx(expected)

    def test_mape_handles_zeros_in_true(self):
        y_true = np.array([0, 100, 200])
        y_pred = np.array([0, 110, 210])
        # eps=1e-9 prevents division by zero
        result = mape(y_true, y_pred)
        assert np.isfinite(result)
        assert result >= 0

    def test_mape_list_input(self):
        y_true = [10, 20, 30]
        y_pred = [12, 22, 32]
        result = mape(y_true, y_pred)
        expected = np.mean([0.2, 0.1, 0.0666667]) * 100
        assert result == pytest.approx(expected, rel=0.01)

    def test_mape_returns_positive(self):
        y_true = np.array([100, 200])
        y_pred = np.array([90, 220])
        result = mape(y_true, y_pred)
        assert result > 0

    def test_mape_single_element(self):
        y_true = np.array([100])
        y_pred = np.array([105])
        assert mape(y_true, y_pred) == pytest.approx(5.0)


class TestEvaluateModel:
    def test_evaluate_model_returns_expected_keys(self, sample_feature_df):
        X = sample_feature_df.drop(columns=["consommation"])
        y = sample_feature_df["consommation"]
        model = LinearRegression()
        model.fit(X, y)
        metrics = evaluate_model(model, X, y)
        assert set(metrics.keys()) == {"R2", "RMSE", "MAPE (%)"}

    def test_evaluate_model_perfect_fit(self):
        X = np.array([[1], [2], [3], [4], [5]], dtype=float)
        y = np.array([2, 4, 6, 8, 10], dtype=float)  # y = 2x
        model = LinearRegression()
        model.fit(X, y)
        metrics = evaluate_model(model, X, y)
        assert metrics["R2"] == pytest.approx(1.0, abs=1e-10)
        assert metrics["RMSE"] == pytest.approx(0.0, abs=1e-10)

    def test_evaluate_model_poor_fit(self):
        np.random.seed(42)
        X = np.random.randn(100, 1)
        y = np.random.randn(100)  # Pure noise → no relationship
        model = LinearRegression()
        model.fit(X, y)
        metrics = evaluate_model(model, X, y)
        # R² should be close to 0 for random data
        assert abs(metrics["R2"]) < 0.1

    def test_evaluate_model_rmse_is_non_negative(self, sample_feature_df):
        X = sample_feature_df.drop(columns=["consommation"])
        y = sample_feature_df["consommation"]
        model = LinearRegression()
        model.fit(X, y)
        metrics = evaluate_model(model, X, y)
        assert metrics["RMSE"] >= 0
