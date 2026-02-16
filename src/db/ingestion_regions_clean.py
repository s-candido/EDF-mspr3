import psycopg2
import pandas as pd

from data.db_loader import DB_CONFIG
from features.features import create_region_features
from db.ingestion_clean_data import insert_features

TABLE_REGION_CLEAN = "conso_clean_region"

def create_region_clean_table(conn):
    cur = conn.cursor()

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_REGION_CLEAN} (
            id BIGSERIAL PRIMARY KEY,
            region TEXT,
            consommation FLOAT,
            thermique FLOAT,
            nucleaire FLOAT,
            eolien FLOAT,
            solaire FLOAT,
            hydraulique FLOAT,
            pompage FLOAT,
            bioenergies FLOAT,
            ech_physiques FLOAT,
            year INTEGER,
            month INTEGER,
            day INTEGER,
            hour INTEGER,
            dayofweek INTEGER,
            weekend INTEGER
        );
    """)

    conn.commit()
    cur.close()
    
def insert_region_features(conn, df: pd.DataFrame):
    cur = conn.cursor()

    cols = ",".join(df.columns)
    placeholders = ",".join(["%s"] * len(df.columns))

    query = f"""
        INSERT INTO {TABLE_REGION_CLEAN} ({cols})
        VALUES ({placeholders})
    """

    for _, row in df.iterrows():
        row = row.where(pd.notnull(row), None)
        cur.execute(query, tuple(row))

    conn.commit()
    cur.close()

def ingest_region_clean():

    print("Connexion PostgreSQL")
    conn = psycopg2.connect(**DB_CONFIG)

    create_region_clean_table(conn)

    print("Chargement données régionales")
    df_raw = pd.read_sql("SELECT * FROM eco2mix_region_raw", conn)

    if df_raw.empty:
        print("Aucune donnée régionale")
        conn.close()
        return

    print("Création des features via create_region_features()")
    df_feat = create_region_features(df_raw)

    print("Insertion dans conso_clean_region")
    insert_region_features(conn, df_feat)

    conn.close()
    print("conso_clean_region mise à jour")
