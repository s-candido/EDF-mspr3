
import psycopg2
import hashlib
from pathlib import Path
import pandas as pd

from src.ingestion.downloader import download_and_extract
from src.data.data_loader import _load_single_file

DB_CONFIG = {
    "host": "edf_postgresl",
    "database": "postgres",
    "user": "postgres",
    "password": "postgres",
    "port": 5432,
}

DATA_DIR = "/opt/airflow/dags/src/data_folder"
TARGET_EXT = [".csv", ".xls", ".xlsx"]

TABLE_DATA = "eco2mix_raw"
TABLE_LOG = "eco2mix_files"

COLUMN_RENAME = {
    "hydraulique_fil_de_leeau_eclusee": "hydraulique_fil_de_leau_eclusee",
}

EXPECTED_COLS = [
    "perimetre","nature","date","heures","consommation",
    "prevision_j_1","prevision_j","fioul","charbon","gaz",
    "nucleaire","eolien","solaire","hydraulique","pompage",
    "bioenergies","ech_physiques","taux_de_co2",
    "ech_comm_angleterre","ech_comm_espagne",
    "ech_comm_italie","ech_comm_suisse",
    "ech_comm_allemagne_belgique",
    "fioul_tac","fioul_cogen","fioul_autres",
    "gaz_tac","gaz_cogen","gaz_ccg","gaz_autres",
    "hydraulique_fil_de_leau_eclusee",
    "hydraulique_lacs","hydraulique_step_turbinage",
    "bioenergies_dechets","bioenergies_biomasse",
    "bioenergies_biogaz","stockage_batterie",
    "destockage_batterie","eolien_terrestre",
    "eolien_offshore","source_file"
]

def file_checksum(path: Path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()

def create_tables(conn):
    cur = conn.cursor()

    # table anti-doublons
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_LOG} (
            filename TEXT PRIMARY KEY,
            checksum TEXT,
            ingested_at TIMESTAMP DEFAULT NOW()
        );
    """)

    # table brute
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_DATA} (
            id BIGSERIAL PRIMARY KEY,
            perimetre TEXT,
            nature TEXT,
            date TEXT,
            heures TEXT,
            consommation INTEGER,
            prevision_j_1 INTEGER,
            prevision_j INTEGER,
            fioul INTEGER,
            charbon INTEGER,
            gaz INTEGER,
            nucleaire INTEGER,
            eolien INTEGER,
            solaire INTEGER,
            hydraulique INTEGER,
            pompage INTEGER,
            bioenergies INTEGER,
            ech_physiques INTEGER,
            taux_de_co2 INTEGER,
            ech_comm_angleterre INTEGER,
            ech_comm_espagne INTEGER,
            ech_comm_italie INTEGER,
            ech_comm_suisse INTEGER,
            ech_comm_allemagne_belgique INTEGER,
            fioul_tac INTEGER,
            fioul_cogen INTEGER,
            fioul_autres INTEGER,
            gaz_tac INTEGER,
            gaz_cogen INTEGER,
            gaz_ccg INTEGER,
            gaz_autres INTEGER,
            hydraulique_fil_de_leau_eclusee INTEGER,
            hydraulique_lacs INTEGER,
            hydraulique_step_turbinage INTEGER,
            bioenergies_dechets INTEGER,
            bioenergies_biomasse INTEGER,
            bioenergies_biogaz INTEGER,
            stockage_batterie TEXT,
            destockage_batterie INTEGER,
            eolien_terrestre INTEGER,
            eolien_offshore INTEGER,
            source_file TEXT
        );
    """)

    conn.commit()
    cur.close()

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # normalisation des valeurs invalides
    df = df.replace(["ND", "None", "nan", ""], pd.NA)

    # Normalisation des noms de colonnes foireux
    df = df.rename(columns=COLUMN_RENAME)

    # schéma imposé
    df = df.reindex(columns=EXPECTED_COLS)

    # Typage automatique
    for col in df.columns:
        converted = pd.to_numeric(df[col], errors="coerce")
        ratio_numeric = converted.notna().mean()

        if ratio_numeric > 0.3:
            df[col] = converted
        else:
            df[col] = df[col].astype("string")
            df[col] = df[col].where(df[col].notna(), None)

    return df



def already_ingested(conn, filename, checksum):
    cur = conn.cursor()
    cur.execute(
        f"SELECT 1 FROM {TABLE_LOG} WHERE filename=%s AND checksum=%s",
        (filename, checksum)
    )
    exists = cur.fetchone() is not None
    cur.close()
    return exists


def log_file(conn, filename, checksum):
    cur = conn.cursor()
    cur.execute(
        f"INSERT INTO {TABLE_LOG}(filename, checksum) VALUES (%s,%s)",
        (filename, checksum)
    )
    conn.commit()
    cur.close()

def insert_dataframe(conn, df: pd.DataFrame):
    cur = conn.cursor()

    cols = ",".join(df.columns)
    placeholders = ",".join(["%s"] * len(df.columns))

    query = f"""
        INSERT INTO {TABLE_DATA} ({cols})
        VALUES ({placeholders})
    """

    for _, row in df.iterrows():
        row = row.where(pd.notnull(row), None)
        cur.execute(query, tuple(row))

    conn.commit()
    cur.close()

def ingest_postgres():
    print("Download eco2mix")
    download_and_extract(start_year=2012)

    print("Connexion PostgreSQL")
    conn = psycopg2.connect(**DB_CONFIG)
    create_tables(conn)

    data_path = Path(DATA_DIR)

    for file in data_path.iterdir():
        if file.suffix.lower() not in TARGET_EXT:
            continue

        checksum = file_checksum(file)

        if already_ingested(conn, file.name, checksum):
            print("Skip:", file.name)
            continue

        print("Ingest:", file.name)

        df = _load_single_file(file)

        df = clean_dataframe(df)
        insert_dataframe(conn, df)
        log_file(conn, file.name, checksum)

    conn.close()
    print("INGESTION TERMINÉE")


if __name__ == "__main__":
    ingest_postgres()
