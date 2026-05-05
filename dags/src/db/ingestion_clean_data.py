import psycopg2
import pandas as pd

from src.data.db_loader import load_from_postgres
from src.features.features import create_features


DB_CONFIG = {
    "host": "edf_postgresql",
    "database": "postgres",
    "user": "postgres",
    "password": "postgres",
    "port": 5432,
}

TABLE_NAME = "conso_clean"

def create_table(conn):
    cur = conn.cursor()

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id BIGSERIAL PRIMARY KEY,
            consommation FLOAT,
            prevision_j_1 FLOAT,
            prevision_j FLOAT,
            fioul FLOAT,
            charbon FLOAT,
            gaz FLOAT,
            nucleaire FLOAT,
            eolien FLOAT,
            solaire FLOAT,
            hydraulique FLOAT,
            pompage FLOAT,
            bioenergies FLOAT,
            ech_physiques FLOAT,
            taux_de_co2 FLOAT,
            ech_comm_angleterre FLOAT,
            ech_comm_espagne FLOAT,
            ech_comm_italie FLOAT,
            ech_comm_suisse FLOAT,
            ech_comm_allemagne_belgique FLOAT,
            fioul_tac FLOAT,
            fioul_cogen FLOAT,
            fioul_autres FLOAT,
            gaz_tac FLOAT,
            gaz_cogen FLOAT,
            gaz_ccg FLOAT,
            gaz_autres FLOAT,
            hydraulique_fil_de_leau_eclusee FLOAT,
            hydraulique_lacs FLOAT,
            hydraulique_step_turbinage FLOAT,
            bioenergies_dechets FLOAT,
            bioenergies_biomasse FLOAT,
            bioenergies_biogaz FLOAT,
            destockage_batterie FLOAT,
            eolien_terrestre FLOAT,
            eolien_offshore FLOAT,
            stockage_batterie TEXT,
            year INTEGER,
            hour INTEGER,
            day INTEGER,
            month INTEGER,
            dayofweek INTEGER,
            weekend INTEGER
        );
    """)

    conn.commit()
    cur.close()

def insert_features(conn, df: pd.DataFrame):
    cur = conn.cursor()

    cols = ",".join(df.columns)
    placeholders = ",".join(["%s"] * len(df.columns))

    print(f"[DEBUG] Colonnes à insérer dans {TABLE_NAME}: {list(df.columns)}")

    query = f"""
        INSERT INTO {TABLE_NAME} ({cols})
        VALUES ({placeholders})
    """

    for _, row in df.iterrows():
        row = row.where(pd.notnull(row), None)
        cur.execute(query, tuple(row))

    conn.commit()
    cur.close()
    print(f"[DEBUG] Insertion terminée: {len(df)} lignes")


def ingest_features():
    print(f"Chargement depuis {TABLE_NAME}")
    df_raw = load_from_postgres()

    print("Création des features")
    df_feat = create_features(df_raw)
    df_feat = df_feat.drop(columns=["id"], errors="ignore")

    print("Connexion PostgreSQL")
    conn = psycopg2.connect(**DB_CONFIG)

    print("Création table features")
    create_table(conn)

    print("Reset features table")
    cur = conn.cursor()
    cur.execute(f"TRUNCATE TABLE {TABLE_NAME}")
    conn.commit()
    cur.close()

    print("Insertion features")
    insert_features(conn, df_feat)

    conn.close()
    print("Features chargées dans PostgreSQL")


if __name__ == "__main__":
    ingest_features()
