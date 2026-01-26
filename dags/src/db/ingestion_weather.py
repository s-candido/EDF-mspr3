import psycopg2
import pandas as pd

from src.data.weather_loader import fetch_weather

DB_CONFIG = {
    "host": "edf_postgresl",
    "database": "postgres",
    "user": "postgres",
    "password": "postgres",
    "port": 5432,
}

TABLE_NAME = "weather_data"

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

def ingest_weather(start_date: str, end_date: str):
    print("Fetch météo")
    df = fetch_weather(start_date, end_date)
    
    df["city"] = df.groupby(df.index // (len(df) // df["date"].nunique())).ngroup()

    # Nettoyage types
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

    print("Connexion PostgreSQL")
    conn = psycopg2.connect(**DB_CONFIG)

    print("Création table météo")
    create_table(conn)

    print("Insertion météo")
    insert_weather(conn, df)

    conn.close()
    print("Météo chargée dans PostgreSQL")


if __name__ == "__main__":
    ingest_weather("2020-01-01", "2020-12-31")
