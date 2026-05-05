import uuid
from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.dummy_operator import DummyOperator
from airflow.utils.trigger_rule import TriggerRule

from src.test.performance_test import (
    run_performance_test,
    check_data_availability,
)

MY_LOCAL_ASSETS = "/opt/airflow/dags"
MLFLOW_URL = "http://mlflow:5000"


def check_data_availability_task(**context):
    """Check if test data exists in DB. Pushes availability result via XCom."""
    dag_run_conf = context.get("dag_run").conf or {}

    test_years = dag_run_conf.get("test_years", [])
    test_months = dag_run_conf.get("test_months", [])
    test_days = dag_run_conf.get("test_days")

    availability = check_data_availability(
        years=test_years,
        months=test_months,
        days=test_days,
    )
    return availability


def run_performance_test_task(**context):
    """Airflow task to run performance test with noise injection."""
    dag_run_conf = context.get("dag_run").conf or {}

    test_years = dag_run_conf.get("test_years", [])
    test_months = dag_run_conf.get("test_months", [])
    test_days = dag_run_conf.get("test_days")
    noise_levels = dag_run_conf.get("noise_levels", [0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5])

    results = run_performance_test(
        test_years=test_years,
        test_months=test_months,
        test_days=test_days,
        noise_levels=noise_levels,
        experiment_name="Performance_Test",
    )

    print("\n" + "=" * 60)
    print("PERFORMANCE TEST COMPLETED")
    print("=" * 60)
    print(f"Model Version Tested: {results['model_version']}")
    print(f"Baseline R2: {results['baseline']['R2']:.4f}")
    print(f"Baseline RMSE: {results['baseline']['RMSE']:.4f}")
    print(f"Baseline MAPE: {results['baseline']['MAPE (%)']:.2f}%")
    print(f"MLFlow Run ID: {results['mlflow_run_id']}")
    print("=" * 60)

    return results


with DAG(
    dag_id="performance_test_dag",
    schedule_interval=None,
    start_date=datetime(2022, 3, 3),
    catchup=False,
    description="""
    Performance test DAG with data availability gating.

    Pipeline:
      check_data_availability → data_ready (branch) → run_performance_test → complete
                               ↘ data_missing (warn) ↗

    If data is missing from both agg_conso_meteo_features and
    aggregated_conso_weather, the test is skipped with a warning.

    Trigger the Data Ingestion DAG first to populate the tables.

    DAG params (override via UI or API):
      - test_years:  List of years (e.g. [2020])
      - test_months: List of months (e.g. [1, 2, 3])
      - test_days:   Optional list of days
      - noise_levels: Noise levels to test
    """,
    tags=["test", "mlflow", "performance_test"],
    params={
        "test_years": [2020],
        "test_months": [4],
    },
) as dag:

    start = DummyOperator(task_id="start")

    check_data = PythonOperator(
        task_id="check_data_availability",
        python_callable=check_data_availability_task,
        do_xcom_push=True,
    )

    performance_test = PythonOperator(
        task_id="run_performance_test",
        python_callable=run_performance_test_task,
        do_xcom_push=False,
    )

    complete = DummyOperator(task_id="complete")

    start >> check_data >> performance_test >> complete
