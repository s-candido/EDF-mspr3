from typing import Iterable
from datetime import datetime

import mlflow
import pandas as pd
import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values
from mlflow.pyfunc import load_model
from src.mlflow.pull_model_from_mlflow import get_latest_model_version
from src.batch_prediction.db_utils import create_table_from_dataframe
from airflow import DAG
from mlflow.tracking import MlflowClient

DB_CONFIG = {
    "host": "edf_postgresql",
    "database": "postgres",
    "user": "postgres",
    "password": "postgres",
    "port": 5432,
}

MLFLOW_URL = "http://mlflow:5000"
MODEL_NAME = "MODEL_EDF"

TARGET = "consommation"

def get_latest_model_version(model_name: str) -> int:
    """
    Get the latest version of a model from the MLflow model registry.

    Args:
        model_name (str): The name of the model in the MLflow model registry.

    Returns:
        int: The latest version of the model.
    """
    try:
        client = MlflowClient()
        versions = client.get_latest_versions(model_name, stages=["None", "Staging", "Production"])
        if versions:
            latest_version = max(int(version.version) for version in versions)
            print(f"Latest version of model '{model_name}' is: {latest_version}")
            return latest_version
        else:
            print(f"No versions found for model '{model_name}'.")
            return None
    except Exception as e:
        print(f"Error fetching latest version: {e}")
        return None
    

def batch_prediction(**context):
    """
    Load a model from MLflow, run batch predictions on a SQL table, and store results.

    Args:
        model_name: MLflow model registry name.
        source_table: SQL table containing data to predict.
        prediction_table: SQL table to store predictions.
        feature_columns: List of columns to use as model features.
        db_config: PostgreSQL connection parameters.
        mlflow_url: MLflow tracking URI.
        context: Airflow task context containing dag_run configuration.

    Returns:
        Number of predictions inserted.
    """
    dag_run_conf = context.get('dag_run').conf or {} if context else {}

    model_name = dag_run_conf.get('model_name', [])
    source_table = context.get('source_table')
    prediction_table = context.get('prediction_table')
    feature_columns = context.get('feature_columns', [])
    db_config = context.get('db_config', {})
    mlflow_url = context.get('mlflow_url', MLFLOW_URL)
    selected_years = dag_run_conf.get('selected_years', [])

    print(" --------------  Batch prediction inputs -------------- ")
    print(f"model_name: {context.get('model_name')}")
    print(f"source_table: {context.get('source_table')}")
    print(f"prediction_table: {context.get('prediction_table')}")
    print(f"feature_columns: {list(context.get('feature_columns', []))}")
    print(f"db_config: {context.get('db_config')}")
    print(f"mlflow_url: {context.get('mlflow_url')}")
    print(f"selected_years: {selected_years}")
    mlflow.set_tracking_uri(mlflow_url)

    version = get_latest_model_version(MODEL_NAME)
    if version is None:
        raise ValueError(f"No MLflow model version found for '{model_name}'.")
    model_name = MODEL_NAME
    model_uri = f"models:/{model_name}/{version}"
    model = load_model(model_uri)

    feature_columns = list(feature_columns)
    if not feature_columns:
        raise ValueError("feature_columns must contain at least one column name.")

    conn = psycopg2.connect(**db_config)
    try:
        query = f"SELECT * FROM {source_table}"
        if selected_years:
            years_str = ','.join(map(str, selected_years))
            query += f" WHERE year IN ({years_str})"
        query += ";"
        df = pd.read_sql_query(query, conn)
        if df.empty:
            return 0

        missing = [col for col in feature_columns if col not in df.columns]
        if missing:
            raise ValueError(f"Missing feature columns in '{source_table}': {missing}")

        X = df[feature_columns].copy()
        X = X.replace("ND", pd.NA).fillna(0)
        print(" ----------- Modèle prédit avec ces colonnes ----------- ")
        print(f" ----------- Année {years_str} ----------- ")
        print(X.head())
        print(f"Training on {len(X)} samples with {len(feature_columns)} features")
        predictions = model.predict(X)

        result_df = df[feature_columns].copy()
        result_df["prediction"] = predictions
        result_df["datetime"] = df["datetime"]


        current_date = datetime.now().strftime("%d_%m_%Y")
        prediction_table_name_agg = f"{prediction_table}_{selected_years}_{current_date}"
        
        create_table_from_dataframe(conn, prediction_table_name_agg, result_df)

        insert_query = sql.SQL("INSERT INTO {} ({}) VALUES %s").format(
            sql.Identifier(prediction_table_name_agg),
            sql.SQL(", ").join(sql.Identifier(col) for col in result_df.columns),
        )
        values = result_df.where(pd.notnull(result_df), None).values.tolist()

        with conn.cursor() as cursor:
            execute_values(cursor, insert_query.as_string(conn), values)
        conn.commit()

        return len(result_df)
    finally:
        conn.close()


