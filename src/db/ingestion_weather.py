import psycopg2
import pandas as pd
import time

from data.weather_loader import fetch_weather

DB_CONFIG = {
    "host": "localhost",
    "database": "postgres",
    "user": "postgres",
    "password": "postgres",
    "port": 5441,
}

TABLE_NAME = "weather_data"
TABLE_LOG  = "weather_log"

TABLE_NAME_LIVE= "weather_data_live"
TABLE_LOG_LIVE  = "weather_log_live"

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
    
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME_LIVE} (
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
        CREATE TABLE IF NOT EXISTS {TABLE_LOG_LIVE} (
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

def ingest_weather_live():
    print("Connexion PostgreSQL météo")
    conn = psycopg2.connect(**DB_CONFIG)
    create_table(conn)

    cur = conn.cursor()

    # récupérer la plage live RTE
    cur.execute("""
        SELECT 
            MIN(date || ' ' || heures),
            MAX(date || ' ' || heures)
        FROM eco2mix_live_raw
    """)
    result = cur.fetchone()
    cur.close()

    if not result or not result[0]:
        print("Aucune donnée RTE live en base")
        conn.close()
        return

    start_dt = pd.to_datetime(result[0])
    end_dt   = pd.to_datetime(result[1])

    start_date = start_dt.strftime("%Y-%m-%d")
    end_date   = end_dt.strftime("%Y-%m-%d")

    print(f"Fetch météo du {start_date} au {end_date}")

    # appel API météo
    df = fetch_weather(start_date, end_date)

    if df.empty:
        print("Aucune donnée météo récupérée")
        conn.close()
        return

    # nettoyage
    df["datetime"] = pd.to_datetime(df["date"], utc=True)
    df["datetime"] = df["datetime"].dt.tz_convert(None)
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

    # éviter les doublons météo
    cur = conn.cursor()
    cur.execute(f"SELECT MAX(datetime) FROM {TABLE_NAME_LIVE}")
    last_weather = cur.fetchone()[0]
    cur.close()

    if last_weather:
        df = df[df["datetime"] > last_weather]

    if df.empty:
        print("Aucune nouvelle donnée météo à insérer")
        conn.close()
        return

    insert_weather_live(conn, df)
    print(f"Insertion météo : {len(df)} lignes")

    conn.close()
    print("INGESTION MÉTÉO LIVE TERMINÉE")
    
    
def insert_weather_live(conn, df: pd.DataFrame):
    cur = conn.cursor()

    cols = ",".join(df.columns)
    placeholders = ",".join(["%s"] * len(df.columns))

    query = f"""
        INSERT INTO {TABLE_NAME_LIVE} ({cols})
        VALUES ({placeholders})
    """

    for _, row in df.iterrows():
        row = row.where(pd.notnull(row), None)
        cur.execute(query, tuple(row))

    conn.commit()
    cur.close()
