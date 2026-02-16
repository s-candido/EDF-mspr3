import psycopg2
import pandas as pd

from data.db_loader import DB_CONFIG
from db.ingestion_clean_data import insert_features
from features.features import create_features



TABLE_LIVE_CHECKPOINT = "conso_live_checkpoint"

def create_checkpoint_table(conn):
    cur = conn.cursor()
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_LIVE_CHECKPOINT} (
            id BIGSERIAL PRIMARY KEY,
            last_datetime TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    conn.commit()
    cur.close()

def get_last_checkpoint(conn):
    cur = conn.cursor()
    cur.execute(f"""
        SELECT MAX(last_datetime)
        FROM {TABLE_LIVE_CHECKPOINT}
    """)
    result = cur.fetchone()[0]
    cur.close()
    return pd.to_datetime(result) if result else None

def update_checkpoint(conn, dt):
    cur = conn.cursor()
    cur.execute(f"""
        INSERT INTO {TABLE_LIVE_CHECKPOINT} (last_datetime)
        VALUES (%s)
    """, (dt,))
    conn.commit()
    cur.close()

def ingest_live_into_conso_clean():
    print("Connexion PostgreSQL")
    conn = psycopg2.connect(**DB_CONFIG)

    create_checkpoint_table(conn)

    df_live = pd.read_sql(
        "SELECT * FROM eco2mix_live_raw",
        conn
    )
    
    if df_live.empty:
        print("Aucune donnée live")
        conn.close()
        return

    df_live["datetime"] = pd.to_datetime(
        df_live["date"].astype(str) + " " + df_live["heures"].astype(str),
        errors="coerce"
    )

    last_checkpoint = get_last_checkpoint(conn)

    if last_checkpoint:
        df_live = df_live[df_live["datetime"] > last_checkpoint]

    if df_live.empty:
        print("Aucune nouvelle heure live")
        conn.close()
        return

    df_feat = create_features(df_live)

    print("Insertion dans conso_clean")
    insert_features(conn, df_feat)

    max_dt = df_live["datetime"].max()
    update_checkpoint(conn, max_dt)

    conn.close()
    print("Live intégré dans conso_clean")
