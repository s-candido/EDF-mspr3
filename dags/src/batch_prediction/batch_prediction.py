from typing import Iterable
from datetime import datetime

import pandas as pd
import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values
from src.batch_prediction.db_utils import create_table_from_dataframe
from airflow import DAG
from src.mlflow.mlflow_utils import get_client, resolve_experiment_and_model

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

def batch_prediction(**context):
    """
    Load a model from an MLflow experiment, run batch predictions, and store results.

    Args:
        source_table: SQL table containing data to predict.
        prediction_table: SQL table to store predictions.
        feature_columns: List of columns to use as model features.
        db_config: PostgreSQL connection parameters.
        mlflow_url: MLflow tracking URI.
        context: Airflow task context containing dag_run configuration.
        model_exp (dag_run.conf): MLflow experiment name (empty = auto-detect latest).
        fallback_model (dag_run.conf): Use fallback model instead of best (default True).

    Returns:
        Number of predictions inserted.
    """
    dag_run_conf = context.get('dag_run').conf or {} if context else {}

    source_table = context.get('source_table')
    prediction_table = context.get('prediction_table')
    feature_columns = context.get('feature_columns', [])
    db_config = context.get('db_config', {})
    mlflow_url = context.get('mlflow_url', MLFLOW_URL)
    selected_years = dag_run_conf.get('selected_years', [])
    selected_months = dag_run_conf.get('selected_months', [])
    selected_days = dag_run_conf.get('selected_days', [])
    experiment_name = dag_run_conf.get('model_exp', '')
    use_fallback = dag_run_conf.get('fallback_model', True)

    print(" --------------  Batch prediction inputs -------------- ")
    print(f"source_table: {context.get('source_table')}")
    print(f"prediction_table: {context.get('prediction_table')}")
    print(f"feature_columns: {list(context.get('feature_columns', []))}")
    print(f"db_config: {context.get('db_config')}")
    print(f"mlflow_url: {context.get('mlflow_url')}")
    print(f"selected_years: {selected_years}")
    print(f"selected_months: {selected_months}")
    print(f"selected_days: {selected_days}")
    print(f"experiment_name: '{experiment_name}' (empty=auto-detect)")
    print(f"use_fallback: {use_fallback}")


    client = get_client(mlflow_url)
    resolved_exp, run, artifact_path, model = resolve_experiment_and_model(
        client,
        experiment_name=experiment_name,
        use_fallback=use_fallback,
    )
    run_id = run.info.run_id
    print(f"Using model '{artifact_path}' from run {run_id} (experiment: {resolved_exp})")

    feature_columns = list(feature_columns)
    if not feature_columns:
        raise ValueError("feature_columns must contain at least one column name.")

    conn = psycopg2.connect(**db_config)
    try:
        query = f"SELECT * FROM {source_table}"
        if selected_years:
            years_str = ','.join(map(str, selected_years))
            query += f" WHERE year IN ({years_str})"

        if selected_months:
            months_str = ','.join(map(str, selected_months))
            if 'WHERE' in query:
                query += f" AND month IN ({months_str})"

        if selected_days:
            days_str = ','.join(map(str, selected_days))
            if 'WHERE' in query:
                query += f" AND day IN ({days_str})"

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
        print(f" ----------- Année : {years_str} ----------- ")
        print(f" ----------- Mois :  {months_str} ----------- ")
        print(f" ----------- Jour :  {days_str} ----------- ")
        print(X.head())
        print(f"Training on {len(X)} samples with {len(feature_columns)} features")
        predictions = model.predict(X)

        result_df = df[feature_columns].copy()
        result_df["prediction"] = predictions
        result_df["datetime"] = df["datetime"]


        current_date = datetime.now().strftime("%d_%m_%Y")
        run_date = datetime.fromtimestamp(run.info.start_time / 1000).strftime("%Y%m%d")
        prediction_table_name_agg = f"{prediction_table}_{selected_years}_{current_date}_{artifact_path}_{run_date}"
        
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


