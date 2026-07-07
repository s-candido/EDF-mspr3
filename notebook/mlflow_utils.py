"""
Shared MLflow utility functions for DAGs.

Covers: experiment resolution, run discovery, model loading from experiments,
and experiment creation for training workflows.

Usage:
    from src.mlflow.mlflow_utils import (
        get_client,
        get_latest_experiment,
        get_experiment,
        get_latest_run,
        resolve_model_artifact,
        load_model_from_run,
        resolve_experiment_and_model,
        create_experiment_and_start_run,
    )
"""

from datetime import datetime
from typing import Any, Optional, Tuple

import mlflow
from mlflow.tracking import MlflowClient
from mlflow.pyfunc import load_model

DEFAULT_MLFLOW_URL = "http://mlflow:5000"
DEFAULT_MODEL_NAME = "MODEL_EDF"


def get_client(mlflow_url: str = DEFAULT_MLFLOW_URL) -> MlflowClient:
    """Create an MlflowClient with the given tracking URI."""
    mlflow.set_tracking_uri(mlflow_url)
    return MlflowClient(tracking_uri=mlflow_url)


def get_latest_experiment(
    client: MlflowClient,
    prefix: str = DEFAULT_MODEL_NAME + "_",
) -> Optional[str]:
    """Find the latest experiment whose name starts with the given prefix.

    Returns the experiment name, or None if no match is found.
    """
    experiments = client.search_experiments(
        view_type=mlflow.entities.ViewType.ACTIVE_ONLY,
        order_by=["creation_time DESC"],
        max_results=10,
    )
    for exp in experiments:
        if exp.name.startswith(prefix):
            return exp.name
    return None


def get_experiment(client: MlflowClient, name: str):
    """Get an experiment by name.  Raises ValueError if not found."""
    exp = client.get_experiment_by_name(name)
    if not exp:
        raise ValueError(f"Experiment '{name}' not found")
    return exp


def get_latest_run(client: MlflowClient, experiment_id: str):
    """Get the most recent run in an experiment (sorted by start_time DESC).

    Raises ValueError if the experiment has no runs.
    """
    runs = client.search_runs(
        experiment_ids=[experiment_id],
        order_by=["attribute.start_time DESC"],
        max_results=1,
    )
    if not runs:
        raise ValueError(
            f"No runs found for experiment ID '{experiment_id}'"
        )
    return runs[0]


def resolve_model_artifact(
    run,
    use_fallback: bool = False,
    default_artifact: str = DEFAULT_MODEL_NAME,
) -> str:
    """Determine which model artifact to load from a run.

    When use_fallback=True, reads 'fallback_model_type' from the run params
    and returns 'fallback_{type}'.
    Otherwise returns the default artifact name (MODEL_EDF).
    """
    if use_fallback:
        fallback_type = run.data.params.get("fallback_model_type", "")
        if not fallback_type:
            raise ValueError(
                "No fallback model in this run. "
                "Train with a fallback enabled, or set fallback_model=False."
            )
        return f"fallback_{fallback_type}"
    return default_artifact


def load_model_from_run(run_id: str, artifact_path: str):
    """Load a PyFunc model from a run's artifact path.

    Args:
        run_id: MLflow run ID.
        artifact_path: Path within the run's artifacts (e.g. 'MODEL_EDF').

    Returns:
        Loaded pyfunc model.
    """
    model_uri = f"runs:/{run_id}/{artifact_path}"
    return load_model(model_uri)


def resolve_experiment_and_model(
    client: MlflowClient,
    experiment_name: str = "",
    use_fallback: bool = False,
    default_artifact: str = DEFAULT_MODEL_NAME,
) -> Tuple[str, Any, str, Any]:
    """One-shot: resolve an experiment -> get its latest run -> load the model.

    If *experiment_name* is empty, auto-detects the latest experiment whose
    name starts with ``{default_artifact}_`` (e.g. ``MODEL_EDF_RandomForest_...``).

    Returns:
        Tuple of ``(experiment_name, run, artifact_path, model)``
    """
    resolved = experiment_name
    if not resolved:
        resolved = get_latest_experiment(client, prefix=default_artifact + "_")
        if not resolved:
            raise ValueError(
                f"No {default_artifact}_* experiment found. "
                "Run the training DAG first."
            )
        print(f"Auto-detected latest experiment: {resolved}")

    exp = get_experiment(client, resolved)
    run = get_latest_run(client, exp.experiment_id)
    artifact = resolve_model_artifact(run, use_fallback, default_artifact)
    model = load_model_from_run(run.info.run_id, artifact)

    return resolved, run, artifact, model


def create_experiment_and_start_run(
    experiment_name: str,
    run_name: str,
    mlflow_url: str = DEFAULT_MLFLOW_URL,
) -> Tuple[str, Any]:
    """Create a new MLflow experiment and start a run inside it.

    The caller should call ``mlflow.end_run()`` after all logging is complete,
    or use ``mlflow.active_run()`` to access the current run inside the active
    context.

    Returns:
        Tuple of ``(experiment_id, active_run)``
    """
    mlflow.set_tracking_uri(mlflow_url)
    experiment_id = mlflow.create_experiment(experiment_name)
    active_run = mlflow.start_run(
        experiment_id=experiment_id,
        run_name=run_name,
    )
    return experiment_id, active_run
