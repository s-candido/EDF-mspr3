import psycopg2
import pandas as pd
import time

from src.data.weather_loader import fetch_weather

DB_CONFIG = {
    "host": "edf_postgresql",
    "database": "postgres",
    "user": "postgres",
    "password": "postgres",
    "port": 5432,
}

TABLE_NAME = "weather_data"
TABLE_LOG  = "weather_log"

def create_table(conn):
    cur = conn.cursor()

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id BIGSERIAL PRIMARY KEY,
            city TEXT,
            datetime TIMESTAMP,
            temperature_2m FLOAT,
            relative_humidity_2m FLOAT,
            snowfall FLOAT,
            precipitation FLOAT,
            weather_code INTEGER
        );
    """)
    
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_LOG} (
            year INTEGER PRIMARY KEY,
            ingested_at TIMESTAMP DEFAULT NOW()
        );
    """)

    conn.commit()
    cur.close()

def already_ingested(conn, year):
    cur = conn.cursor()
    cur.execute(
        f"SELECT 1 FROM {TABLE_LOG} WHERE year=%s",
        (year,)
    )
    exists = cur.fetchone() is not None
    cur.close()
    return exists


def log_year(conn, year):
    cur = conn.cursor()
    cur.execute(
        f"INSERT INTO {TABLE_LOG}(year) VALUES (%s)",
        (year,)
    )
    conn.commit()
    cur.close()


def insert_weather(conn, df: pd.DataFrame):
    cur = conn.cursor()

    cols = ",".join(df.columns)
    placeholders = ",".join(["%s"] * len(df.columns))

    query = f"""
        INSERT INTO {TABLE_NAME} ({cols})
        VALUES ({placeholders})
    """

    for _, row in df.iterrows():
        row = row.where(pd.notnull(row), None)
        cur.execute(query, tuple(row))

    conn.commit()
    cur.close()

def ingest_weather(start_year=2012, end_year=2023):
    print("Connexion PostgreSQL")
    conn = psycopg2.connect(**DB_CONFIG)
    create_table(conn)

    for year in range(start_year, end_year + 1):

        if already_ingested(conn, year):
            print("Skip weather", year)
            continue

        print("Fetch météo", year)

        start_date = f"{year}-01-01"
        end_date   = f"{year}-12-31"

        df = fetch_weather(start_date, end_date)

        # Nettoyage
        df["datetime"] = pd.to_datetime(df["date"])
        df = df.drop(columns=["date"])

        df = df[[
            "city",
            "datetime",
            "temperature_2m",
            "relative_humidity_2m",
            "snowfall",
            "precipitation",
            "weather_code"
        ]]

        print("Insertion météo", year)
        insert_weather(conn, df)
        log_year(conn, year)

        print("Sleep")
        time.sleep(2)

    conn.close()
    print("ingestion weather terminée")



if __name__ == "__main__":
    ingest_weather("2020-01-01", "2020-12-31")
