import uuid
import json
from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.dummy_operator import DummyOperator

import sys
import os
import psycopg2
import pandas as pd
import mlflow
import mlflow.sklearn
from sklearn.model_selection import train_test_split

sys.path.append('/opt/airflow/dags/src')

from src.modeling.train import train_models
from src.modeling.evaluate import evaluate_model
from src.batch_prediction.data_prep import prepare_batch_prediction_data

correlation_id = uuid.uuid4()
MY_LOCAL_ASSETS = "/opt/airflow/dags"
MLFLOW_URL= "http://mlflow:5000"
SOURCE_TABLE = "aggregated_conso_weather"
PREDICTION_TABLE = "batch_predictions"
FEATURE_COLUMNS = [
    "temp_fr",
    "snow_fr",
    "hour",
    "month",
    "dayofweek",
    "weekend",
]
UTILS_COLUMNS = [
    "id",
    "conso_id",
    "datetime",
    "year",
    "day"
]
TARGET = "consommation"

DB_CONFIG = {
    "host": "edf_postgresql",
    "database": "postgres",
    "user": "postgres",
    "password": "postgres",
    "port": 5432,
}

MODEL_NAME = "MODEL_EDF"

def train_and_log_model(**context):
    dag_run_conf = context.get('dag_run').conf or {}
    selected_years = dag_run_conf.get('selected_years', [])
    selected_months = dag_run_conf.get('selected_months', [])
    selected_days = dag_run_conf.get('selected_days', [])
    
    conn = psycopg2.connect(**DB_CONFIG)

    feature_columns = list(FEATURE_COLUMNS)
    if not feature_columns:
        raise ValueError("feature_columns must contain at least one column name.")

    query = f"SELECT * FROM {SOURCE_TABLE}"
    conditions = []
    if selected_years:
        years_str = ','.join(map(str, selected_years))
        conditions.append(f"year IN ({years_str})")
    if selected_months:
        months_str = ','.join(map(str, selected_months))
        conditions.append(f"month IN ({months_str})")
    if selected_days:
        days_str = ','.join(map(str, selected_days))
        conditions.append(f"day IN ({days_str})")
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY year, month, day, hour"
    
    print(f"Executing query: {query}")
    df = pd.read_sql(query, conn)
    conn.close()
    
    print(f"Loaded {len(df)} records from {SOURCE_TABLE} for years={selected_years} months={selected_months} days={selected_days}")

    data_min_date = df['datetime'].min()
    data_max_date = df['datetime'].max()
    print(f"Data timespan: {data_min_date} → {data_max_date}")
    
    if df is None or df.empty:
        raise ValueError("No data available for training")
    
    TARGET = "consommation"
    df[TARGET] = pd.to_numeric(df[TARGET], errors="coerce")
    
    X = df[feature_columns].fillna(0)
    y = df[TARGET].fillna(0)
    print(" ----------- Modèle entrainé avec ces colonnes ----------- ")
    print(X.head())
    print(f"Training on {len(X)} samples with {len(FEATURE_COLUMNS)} features")
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    
    models = train_models(X_train, y_train)
    
    ranked = []
    for name, model in models.items():
        metrics = evaluate_model(model, X_test, y_test)
        print(f"Model: {name}")
        for k, v in metrics.items():
            print(f"  {k}: {v:.4f}")
        ranked.append((metrics["R2"], name, model))

    ranked.sort(key=lambda x: x[0], reverse=True)
    best_r2, best_name, best_model = ranked[0]
    fallback_r2, fallback_name, fallback_model = ranked[1] if len(ranked) > 1 else (None, None, None)
    print(f"Best model: {best_name} (R2={best_r2:.4f})")
    if fallback_name:
        print(f"Fallback model: {fallback_name} (R2={fallback_r2:.4f})")
    else:
        print("No fallback model")

    mlflow.set_tracking_uri(MLFLOW_URL)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    experiment_name = f"{MODEL_NAME}_{best_name}_{timestamp}"
    experiment_id = mlflow.create_experiment(experiment_name)

    with mlflow.start_run(experiment_id=experiment_id, run_name=f"training_{best_name}_{timestamp}"):
        # ── Model metadata ──
        mlflow.log_param("model_type", best_name)
        mlflow.log_param("model_label", f"{MODEL_NAME}_{best_name}")
        mlflow.log_param("selected_years", str(selected_years))
        mlflow.log_param("selected_months", str(selected_months))
        mlflow.log_param("selected_days", str(selected_days))
        mlflow.log_param("n_samples", len(X_train))
        mlflow.log_param("n_features", len(FEATURE_COLUMNS))
        mlflow.log_param("features", FEATURE_COLUMNS)
        mlflow.log_param("correlation_id", str(correlation_id))

        # ── Data timespan the model was trained on ──
        mlflow.log_param("data_start_date", str(data_min_date))
        mlflow.log_param("data_end_date", str(data_max_date))

        # ── Hyperparameters (including defaults) ──
        hyperparams = {}
        try:
            hyperparams = best_model.get_params()
            mlflow.log_params({f"hp_{k}": str(v) for k, v in hyperparams.items()})
        except Exception as e:
            print(f"Could not log hyperparameters: {e}")

        # ── Tags ──
        mlflow.set_tag("model_label", f"{MODEL_NAME}_{best_name}")
        mlflow.set_tag("training_data_range", f"{data_min_date} → {data_max_date}")
        mlflow.set_tag("selected_filters", f"years={selected_years} months={selected_months} days={selected_days}")

        final_metrics = evaluate_model(best_model, X_test, y_test)
        mlflow.log_metric("R2", final_metrics['R2'])
        mlflow.log_metric("RMSE", final_metrics['RMSE'])
        mlflow.log_metric("MAPE", final_metrics['MAPE (%)'])

        mlflow.sklearn.log_model(best_model, artifact_path=MODEL_NAME)

        model_uri = f"runs:/{mlflow.active_run().info.run_id}/{MODEL_NAME}"
        mlflow.register_model(model_uri, MODEL_NAME)

        print(f"Modèle retenu : {best_name} (R2={best_r2:.4f})")
        print(f"Best model registered in MLflow as '{MODEL_NAME}' - Run ID: {mlflow.active_run().info.run_id}")

        if fallback_model is not None:
            mlflow.log_param("fallback_model_type", fallback_name)
            mlflow.log_param("fallback_r2", fallback_r2)
            fallback_metrics = evaluate_model(fallback_model, X_test, y_test)
            mlflow.log_metric("fallback_R2", fallback_metrics['R2'])
            mlflow.log_metric("fallback_RMSE", fallback_metrics['RMSE'])
            mlflow.log_metric("fallback_MAPE", fallback_metrics['MAPE (%)'])

            try:
                fallback_hp = fallback_model.get_params()
                mlflow.log_params({f"fallback_hp_{k}": str(v) for k, v in fallback_hp.items()})
            except Exception as e:
                print(f"Could not log fallback hyperparameters: {e}")

            mlflow.sklearn.log_model(fallback_model, artifact_path=f"fallback_{fallback_name}")

            fallback_reg_name = f"fallback_{fallback_name}_{timestamp}"
            fallback_uri = f"runs:/{mlflow.active_run().info.run_id}/fallback_{fallback_name}"
            mlflow.register_model(fallback_uri, fallback_reg_name)

            print(f"Fallback model: {fallback_name} (R2={fallback_r2:.4f})")
            print(f"Fallback model registered in MLflow as '{fallback_reg_name}'")

        print(f"Training data range: {data_min_date} → {data_max_date}")
        print(f"Hyperparameters (best): {hyperparams}")
        print(f"Model and artifacts logged to MLflow with correlation_id: {correlation_id}")
        print(f"MLflow experiment: {experiment_name}")

    return {
        "model_name": best_name,
        "r2_score": best_r2,
        "correlation_id": str(correlation_id),
        "fallback_model_name": fallback_name,
        "fallback_r2": fallback_r2,
        "experiment_name": experiment_name,
    }

with DAG(
    dag_id="training_dag",
    schedule_interval=None,
    start_date=datetime(2022, 3, 3),
    catchup=False,
    description="DAG for training ML models on selected years/months/days from aggregated_conso_weather table",
    tags=["training", "mlflow", "postgresql"],
    params={
        "selected_years": [2020, 2021, 2022],
        "selected_months": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
        "selected_days": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31],
    }
    
) as dag:

    start = DummyOperator(task_id="start")

    prepare_data_job = PythonOperator(
        task_id="prepare_data_job",
        python_callable=prepare_batch_prediction_data,
        op_kwargs={
            "source_table": SOURCE_TABLE,
            "prepared_table": "agg_conso_meteo_features",
            "feature_columns": FEATURE_COLUMNS,
            "utils_columns": UTILS_COLUMNS,
            "target": TARGET,
        },
        do_xcom_push=False,
        dag=dag,
    )

    train_model_task = PythonOperator(
        task_id="train_model_task", 
        python_callable=train_and_log_model,
        do_xcom_push=False,
        dag=dag
    )

    complete = DummyOperator(task_id="complete")

    start >> prepare_data_job >> train_model_task >> complete