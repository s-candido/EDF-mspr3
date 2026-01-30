from typing import Iterable

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from src.batch_prediction.db_utils import create_table_from_dataframe


DB_CONFIG = {
    "host": "edf_postgresql",
    "database": "postgres",
    "user": "postgres",
    "password": "postgres",
    "port": 5432,
}


def prepare_batch_prediction_data(
    source_table: str,
    prepared_table: str,
    feature_columns: Iterable[str],
    utils_columns: Iterable[str] = None,
    target: str = None,
    db_config: dict = DB_CONFIG,
) -> int:
    """
    Load raw data from PostgreSQL, select features, clean values, and persist to a staging table.

    Args:
        source_table: SQL table containing raw data to predict.
        prepared_table: SQL table to store prepared features.
        feature_columns: List of columns to use as model features.
        utils_columns: List of utility columns to preserve (id, conso_id, datetime) but exclude from features.
        target: Target column name (e.g., 'consommation') to preserve but exclude from features.
        db_config: PostgreSQL connection parameters.

    Returns:
        Number of prepared rows inserted.
    """
    feature_columns = list(feature_columns)
    utils_columns = list(utils_columns) if utils_columns else []
    
    if not feature_columns:
        raise ValueError("feature_columns must contain at least one column name.")
    
    # All columns to select from source table
    all_columns = feature_columns + utils_columns
    if target:
        all_columns.append(target)

    conn = psycopg2.connect(**db_config)
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = %s
                );
            """, (prepared_table,))
            table_exists = cursor.fetchone()[0]
        
        if table_exists:
            print(f"Table '{prepared_table}' already exists. Skipping data preparation.")
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM {prepared_table}")
                existing_count = cursor.fetchone()[0]
            print(f"Existing table contains {existing_count} rows.")
            return existing_count

        columns_str = ', '.join(all_columns)
        df = pd.read_sql_query(f"SELECT {columns_str} FROM {source_table};", conn)
        if df.empty:
            return 0

        missing = [col for col in all_columns if col not in df.columns]
        if missing:
            raise ValueError(f"Missing columns in '{source_table}': {missing}")

        # Prepare features (excluding utility columns and target)
        X = df[feature_columns].copy()
        X = X.replace("ND", pd.NA).fillna(0)

        # Create prepared data with utility columns, target (if exists), and features
        prepared_df = X.copy()
        
        # Add utility columns to prepared data
        for col in utils_columns:
            if col in df.columns:
                prepared_df[col] = df[col]
        
        # Add target column to prepared data if specified
        if target and target in df.columns:
            prepared_df[target] = df[target]

        create_table_from_dataframe(conn, prepared_table, prepared_df)

        with conn.cursor() as cursor:
            cursor.execute(f"TRUNCATE TABLE {prepared_table}")
        conn.commit()

        values = prepared_df.where(pd.notnull(prepared_df), None).values.tolist()
        columns_sql = ", ".join(prepared_df.columns)
        insert_query = f"INSERT INTO {prepared_table} ({columns_sql}) VALUES %s"

        with conn.cursor() as cursor:
            execute_values(cursor, insert_query, values)
        conn.commit()

        return len(prepared_df)
    finally:
        conn.close()
