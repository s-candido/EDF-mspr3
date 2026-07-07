"""
Tests for dags/src/mlflow/mlflow_utils.py.

Covers: resolve_model_artifact, create_experiment_and_start_run
These are used by the training_dag and batch_prediction_dag.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import MagicMock, patch

from src.mlflow.mlflow_utils import (
    resolve_model_artifact,
    get_client,
    create_experiment_and_start_run,
)


class TestResolveModelArtifact:
    def test_default_artifact_without_fallback(self):
        run = MagicMock()
        run.data.params = {}
        result = resolve_model_artifact(run, use_fallback=False)
        assert result == "MODEL_EDF"

    def test_default_artifact_custom_name(self):
        run = MagicMock()
        run.data.params = {}
        result = resolve_model_artifact(run, use_fallback=False, default_artifact="CUSTOM_MODEL")
        assert result == "CUSTOM_MODEL"

    def test_fallback_with_fallback_type(self):
        run = MagicMock()
        run.data.params = {"fallback_model_type": "RandomForest"}
        result = resolve_model_artifact(run, use_fallback=True)
        assert result == "fallback_RandomForest"

    def test_fallback_without_type_raises(self):
        run = MagicMock()
        run.data.params = {}
        with pytest.raises(ValueError, match="No fallback model"):
            resolve_model_artifact(run, use_fallback=True)

    def test_fallback_with_default_artifact_uses_default(self):
        run = MagicMock()
        run.data.params = {}
        result = resolve_model_artifact(run, use_fallback=False, default_artifact="MY_MODEL")
        assert result == "MY_MODEL"


class TestGetClient:
    @patch("src.mlflow.mlflow_utils.mlflow.set_tracking_uri")
    @patch("src.mlflow.mlflow_utils.MlflowClient")
    def test_get_client_sets_tracking_uri(self, MockClient, mock_set_uri):
        get_client("http://mlflow-custom:5000")
        mock_set_uri.assert_called_once_with("http://mlflow-custom:5000")

    @patch("src.mlflow.mlflow_utils.mlflow.set_tracking_uri")
    @patch("src.mlflow.mlflow_utils.MlflowClient")
    def test_get_client_returns_client(self, MockClient, mock_set_uri):
        client = get_client()
        assert client is not None

    @patch("src.mlflow.mlflow_utils.mlflow.set_tracking_uri")
    @patch("src.mlflow.mlflow_utils.MlflowClient")
    def test_get_client_default_url(self, MockClient, mock_set_uri):
        get_client()
        mock_set_uri.assert_called_once_with("http://mlflow:5000")


class TestCreateExperimentAndStartRun:
    @patch("src.mlflow.mlflow_utils.mlflow.set_tracking_uri")
    @patch("src.mlflow.mlflow_utils.mlflow.create_experiment")
    @patch("src.mlflow.mlflow_utils.mlflow.start_run")
    def test_creates_experiment_and_run(self, mock_start_run, mock_create_exp, mock_set_uri):
        mock_create_exp.return_value = "exp_123"
        mock_start_run.return_value = MagicMock()

        exp_id, run = create_experiment_and_start_run(
            "Test_Experiment", "test_run_001", "http://mlflow:5000"
        )

        mock_set_uri.assert_called_once_with("http://mlflow:5000")
        mock_create_exp.assert_called_once_with("Test_Experiment")
        mock_start_run.assert_called_once_with(
            experiment_id="exp_123", run_name="test_run_001"
        )
        assert exp_id == "exp_123"

