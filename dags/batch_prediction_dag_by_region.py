from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.dummy_operator import DummyOperator

from src.pipelines.prediction_consommation_regions import (
    build_all_region_feature_tables,
    train_all_region_models,
    predict_all_regions,
    DB_CONFIG,
    MLFLOW_URL,
    FEATURE_COLUMNS,
)

DAG_NAME = "batch_prediction_dag_by_region"

default_args = {
    "owner": "airflow",
}


def build_feature_tables_task(**context):
    """Phase 1: Build per-region feature tables in PostgreSQL."""
    dag_run_conf = context.get("dag_run").conf or {}
    regions = dag_run_conf.get("regions", None)
    rebuild = dag_run_conf.get("rebuild_features", False)

    result = build_all_region_feature_tables(
        db_config=DB_CONFIG,
        regions=regions,
        replace=rebuild,
    )
    print(f"Feature tables created: {len(result)}")
    for region, table in result.items():
        print(f"  {region} -> {table}")
    return result


def train_region_models_task(**context):
    """Phase 2: Train per-region models and log to MLflow."""
    ti = context["task_instance"]
    feature_tables = ti.xcom_pull(
        task_ids="build_feature_tables_task", key="return_value"
    )
    if not feature_tables:
        raise ValueError("No feature tables found from build_feature_tables_task")

    results = train_all_region_models(
        feature_tables=feature_tables,
        db_config=DB_CONFIG,
        mlflow_url=MLFLOW_URL,
        feature_columns=FEATURE_COLUMNS,
    )

    n_trained = sum(1 for r in results if r.get("status") == "success")
    n_skipped = sum(1 for r in results if r.get("status") == "skipped")
    print(f"Training complete: {n_trained} trained, {n_skipped} skipped")
    return results


def predict_consumption_task(**context):
    """Phase 3: Run batch predictions per region and store results."""
    ti = context["task_instance"]
    feature_tables = ti.xcom_pull(
        task_ids="build_feature_tables_task", key="return_value"
    )
    if not feature_tables:
        raise ValueError("No feature tables found from build_feature_tables_task")

    dag_run_conf = context.get("dag_run").conf or {}
    selected_years = dag_run_conf.get("selected_years", [2020])
    selected_months = dag_run_conf.get("selected_months", None)
    selected_days = dag_run_conf.get("selected_days", None)

    result = predict_all_regions(
        feature_tables=feature_tables,
        db_config=DB_CONFIG,
        mlflow_url=MLFLOW_URL,
        feature_columns=FEATURE_COLUMNS,
        selected_years=selected_years,
        selected_months=selected_months,
        selected_days=selected_days,
    )

    if result.get("status") == "success":
        print(f"Predictions stored in: {result['prediction_table']}")
        print(f"Total rows: {result['n_rows']}")
        print(f"Regions: {result['n_regions']}")
    else:
        print(f"Prediction result: {result}")

    return result


with DAG(
    dag_id=DAG_NAME,
    default_args=default_args,
    schedule_interval=None,
    start_date=datetime(2022, 3, 3),
    catchup=False,
    description="""
    Per-region batch prediction pipeline.

    Pipeline:
      build_feature_tables → train_region_models → predict_consumption

    Phases:
      1. Build per-region feature tables (agg_conso_meteo_features_{region})
      2. Train per-region models          (→ MLflow Model Registry)
      3. Batch predict per region          (→ batch_predictions_* table)

    DAG params (override via UI or API):
      - regions:          List of regions (default: all 12 regions)
      - rebuild_features: Recreate feature tables (default: false)
      - selected_years:   Years to predict   (default: [2020])
      - selected_months:  Months to predict  (default: all)
      - selected_days:    Days to predict    (default: all)
    """,
    tags=["prediction", "regions", "mlflow", "postgresql"],
    params={
        "selected_years": [2020],
        "rebuild_features": False,
    },
) as dag:

    start = DummyOperator(task_id="start")

    build_feature_tables = PythonOperator(
        task_id="build_feature_tables_task",
        python_callable=build_feature_tables_task,
        provide_context=True,
        do_xcom_push=True,
    )

    train_region_models = PythonOperator(
        task_id="train_region_models_task",
        python_callable=train_region_models_task,
        provide_context=True,
        do_xcom_push=True,
    )

    predict_consumption = PythonOperator(
        task_id="predict_consumption_task",
        python_callable=predict_consumption_task,
        provide_context=True,
        do_xcom_push=False,
    )

    complete = DummyOperator(task_id="complete")

    start >> build_feature_tables >> train_region_models >> predict_consumption >> complete
