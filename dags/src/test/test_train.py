"""
Tests for dags/src/modeling/train.py.

Covers: train_models
Used by the training_dag and ml_pipeline_dag.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor

from src.modeling.train import train_models


class TestTrainModels:
    def test_train_models_returns_dict(self, sample_feature_df):
        X = sample_feature_df.drop(columns=["consommation"])
        y = sample_feature_df["consommation"]
        models = train_models(X, y)
        assert isinstance(models, dict)

    def test_train_models_contains_expected_keys(self, sample_feature_df):
        X = sample_feature_df.drop(columns=["consommation"])
        y = sample_feature_df["consommation"]
        models = train_models(X, y)
        expected = {"LinearRegression", "RandomForest", "KNN", "XGBoost", "Prophet"}
        assert set(models.keys()) == expected

    def test_train_models_returns_fitted_models(self, sample_feature_df):
        X = sample_feature_df.drop(columns=["consommation"])
        y = sample_feature_df["consommation"]
        models = train_models(X, y)
        for name, model in models.items():
            # sklearn check: model has been fitted
            try:
                # Most sklearn models store n_features_in_ after fit
                assert hasattr(model, "n_features_in_")
                assert model.n_features_in_ == X.shape[1]
            except AttributeError:
                # Some models may not have n_features_in_
                pass

    def test_train_models_linear_regression_is_linear(self, sample_feature_df):
        X = sample_feature_df.drop(columns=["consommation"])
        y = sample_feature_df["consommation"]
        models = train_models(X, y)
        lr = models["LinearRegression"]
        assert isinstance(lr, LinearRegression)

    def test_train_models_random_forest_is_rf(self, sample_feature_df):
        X = sample_feature_df.drop(columns=["consommation"])
        y = sample_feature_df["consommation"]
        models = train_models(X, y)
        rf = models["RandomForest"]
        assert isinstance(rf, RandomForestRegressor)
        assert rf.n_estimators == 200

    def test_train_models_can_predict(self, sample_feature_df):
        X = sample_feature_df.drop(columns=["consommation"])
        y = sample_feature_df["consommation"]
        models = train_models(X, y)
        for name, model in models.items():
            preds = model.predict(X.head(5))
            assert len(preds) == 5
            assert np.all(np.isfinite(preds))

    def test_train_models_with_small_data(self):
        X = np.array([[1], [2], [3], [4], [5], [6], [7], [8]], dtype=float)
        y = np.array([10, 20, 30, 40, 50, 60, 70, 80], dtype=float)
        models = train_models(X, y)
        assert len(models) == 5
        for name, model in models.items():
            pred = model.predict([[9]])
            assert np.isfinite(pred[0])

    def test_train_models_predictions_reasonable(self, sample_feature_df):
        X = sample_feature_df.drop(columns=["consommation"])
        y = sample_feature_df["consommation"]
        models = train_models(X, y)
        y_mean = y.mean()
        for name, model in models.items():
            preds = model.predict(X)
            # Predictions should be within reasonable range of target
            assert preds.mean() == pytest.approx(y_mean, rel=1.0)
