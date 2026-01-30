from typing import Iterable

import mlflow
import pandas as pd
import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values

from src.mlflow.pull_model_from_mlflow import get_latest_model_version
from src.batch_prediction.db_utils import create_table_from_dataframe


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


def batch_prediction(
    model_name: str,
    source_table: str,
    prediction_table: str,
    feature_columns: Iterable[str],
    db_config: dict = DB_CONFIG,
    mlflow_url: str = MLFLOW_URL,
) -> int:
    """
    Load a model from MLflow, run batch predictions on a SQL table, and store results.

    Args:
        model_name: MLflow model registry name.
        source_table: SQL table containing data to predict.
        prediction_table: SQL table to store predictions.
        feature_columns: List of columns to use as model features.
        db_config: PostgreSQL connection parameters.
        mlflow_url: MLflow tracking URI.

    Returns:
        Number of predictions inserted.
    """
    mlflow.set_tracking_uri(mlflow_url)

    version = get_latest_model_version(model_name)
    if version is None:
        raise ValueError(f"No MLflow model version found for '{model_name}'.")

    model_uri = f"models:/{model_name}/{version}"
    model = mlflow.pyfunc.load_model(model_uri)

    feature_columns = list(feature_columns)
    if not feature_columns:
        raise ValueError("feature_columns must contain at least one column name.")

    conn = psycopg2.connect(**db_config)
    try:
        df = pd.read_sql_query(f"SELECT * FROM {source_table};", conn)
        if df.empty:
            return 0

        missing = [col for col in feature_columns if col not in df.columns]
        if missing:
            raise ValueError(f"Missing feature columns in '{source_table}': {missing}")

        X = df[feature_columns].copy()
        X = X.replace("ND", pd.NA).fillna(0)

        predictions = model.predict(X)

        result_df = df[feature_columns].copy()
        result_df["prediction"] = predictions

        create_table_from_dataframe(conn, prediction_table, result_df)

        insert_query = sql.SQL("INSERT INTO {} ({}) VALUES %s").format(
            sql.Identifier(prediction_table),
            sql.SQL(", ").join(sql.Identifier(col) for col in result_df.columns),
        )
        values = result_df.where(pd.notnull(result_df), None).values.tolist()

        with conn.cursor() as cursor:
            execute_values(cursor, insert_query.as_string(conn), values)
        conn.commit()

        return len(result_df)
    finally:
        conn.close()


