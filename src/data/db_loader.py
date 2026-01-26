import psycopg2
import pandas as pd

DB_CONFIG = {
    "host": "localhost",
    "database": "postgres",
    "user": "postgres",
    "password": "postgres",
    "port": 5441
}

def load_from_postgres():
    conn = psycopg2.connect(**DB_CONFIG)
    df = pd.read_sql("SELECT * FROM eco2mix_raw", conn)
    conn.close()
    return df
