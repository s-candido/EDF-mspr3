import uuid
import mlflow
from mlflow.tracking import MlflowClient
from pytest_bdd import scenarios, given, when, then
from sklearn.linear_model import LinearRegression
from sklearn.datasets import make_regression

from tests.deploy.steps.conftest import MLFLOW_URL

scenarios("../features/model_push.feature")

# shared state between Given -> When -> Then steps within a scenario
_scenario_state: dict = {}


@given("MLflow is running and accessible")
def mlflow_available(mlflow_uri):
    assert mlflow_uri is not None


@when("I create an experiment and log a dummy model with a metric")
def log_dummy_model(mlflow_uri):
    mlflow.set_tracking_uri(mlflow_uri)
    client = MlflowClient(tracking_uri=mlflow_uri)

    exp_name = f"TEST_DUMMY_{uuid.uuid4().hex[:8]}"
    exp_id = mlflow.create_experiment(exp_name)

    with mlflow.start_run(experiment_id=exp_id, run_name="dummy-run"):
        X, y = make_regression(n_samples=20, n_features=2, noise=0.1, random_state=42)
        model = LinearRegression()
        model.fit(X, y)

        score = model.score(X, y)
        mlflow.log_metric("r2_score", score)
        mlflow.sklearn.log_model(model, artifact_path="MODEL_EDF")
        run_id = mlflow.active_run().info.run_id

    _scenario_state["exp_name"] = exp_name
    _scenario_state["exp_id"] = exp_id
    _scenario_state["run_id"] = run_id
    _scenario_state["expected_score"] = score


@then("the experiment and run should appear in MLflow")
def verify_experiment_and_run(mlflow_uri):
    client = MlflowClient(tracking_uri=mlflow_uri)
    exp = client.get_experiment(_scenario_state["exp_id"])

    assert exp is not None, "Experiment should exist in MLflow"
    assert exp.name == _scenario_state["exp_name"], (
        f"Expected experiment name '{_scenario_state['exp_name']}', got '{exp.name}'"
    )

    runs = client.search_runs(
        experiment_ids=[_scenario_state["exp_id"]],
        max_results=10,
    )
    assert len(runs) > 0, "At least one run should exist in the experiment"
    run_ids = [r.info.run_id for r in runs]
    assert _scenario_state["run_id"] in run_ids, (
        f"Run {_scenario_state['run_id']} not found in experiment runs"
    )


@then("the logged metric value should be readable")
def verify_metric(mlflow_uri):
    client = MlflowClient(tracking_uri=mlflow_uri)
    run = client.get_run(_scenario_state["run_id"])

    assert "r2_score" in run.data.metrics, (
        f"Metric 'r2_score' not found. Available: {list(run.data.metrics.keys())}"
    )
    actual = run.data.metrics["r2_score"]
    expected = _scenario_state["expected_score"]
    assert abs(actual - expected) < 1e-6, (
        f"Metric 'r2_score' mismatch: expected {expected}, got {actual}"
    )
