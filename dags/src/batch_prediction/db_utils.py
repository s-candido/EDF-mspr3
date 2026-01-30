import pandas as pd
import psycopg2
from psycopg2 import sql


def infer_sql_type(series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series):
        return "BOOLEAN"
    if pd.api.types.is_integer_dtype(series):
        return "INTEGER"
    if pd.api.types.is_float_dtype(series):
        return "DOUBLE PRECISION"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "TIMESTAMP"
    return "TEXT"


def create_table_from_dataframe(
    conn: psycopg2.extensions.connection,
    table_name: str,
    df: pd.DataFrame,
) -> None:
    columns = [
        sql.SQL("{} {}").format(sql.Identifier(col), sql.SQL(infer_sql_type(df[col])))
        for col in df.columns
    ]
    create_query = sql.SQL("CREATE TABLE IF NOT EXISTS {} (")
    create_query = create_query.format(sql.Identifier(table_name))
    create_query = create_query + sql.SQL(", ").join(columns) + sql.SQL(");")

    with conn.cursor() as cursor:
        cursor.execute(create_query)
    conn.commit()
