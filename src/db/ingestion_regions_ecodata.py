import psycopg2
import pandas as pd
from pathlib import Path
import re

from data.data_loader import _load_single_file
from db.ingestion_clean_data import create_table
from ingestion.download_region_data import download_all_regions, get_last_region_year
from db.regions_log import (
    create_region_log_table,
    already_ingested_region,
    log_region_year
)
DB_CONFIG = {
    "host": "localhost",
    "database": "postgres",
    "user": "postgres",
    "password": "postgres",
    "port": 5441,
}

EXPECTED_REGION_COLS = [
    "perimetre",
    "nature",
    "date",
    "heures",
    "consommation",
    "thermique",
    "nucleaire",
    "eolien",
    "solaire",
    "hydraulique",
    "pompage",
    "bioenergies",
    "ech_physiques",
    "region",
    "source_file"
]


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_REGIONS = PROJECT_ROOT / "data_regions"

TABLE_NAME = "eco2mix_region_raw"

def create_region_table(conn):
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS eco2mix_region_raw (
            id BIGSERIAL PRIMARY KEY,
            region TEXT,
            perimetre TEXT,
            nature TEXT,
            date DATE,
            heures TIME,
            consommation FLOAT,
            thermique FLOAT,
            nucleaire FLOAT,
            eolien FLOAT,
            solaire FLOAT,
            hydraulique FLOAT,
            pompage FLOAT,
            bioenergies FLOAT,
            ech_physiques FLOAT,
            source_file TEXT
        );
    """)

    conn.commit()
    cur.close()

def insert_dataframe(conn, df: pd.DataFrame):
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

def extract_region_from_filename(filename: str):
    match = re.search(r"RTE_(.*?)_Annuel", filename)
    return match.group(1) if match else "UNKNOWN"


def clean_region_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # supprimer colonnes Unnamed
    df = df.loc[:, ~df.columns.str.startswith("unnamed")]
    # remplacer ND
    df = df.replace("ND", pd.NA)
    # forcer schéma
    df = df.reindex(columns=EXPECTED_REGION_COLS)

    numeric_cols = [
        "consommation",
        "thermique",
        "nucleaire",
        "eolien",
        "solaire",
        "hydraulique",
        "pompage",
        "bioenergies",
        "ech_physiques"
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df

def ingest_regions(start_year=2012, end_year=2023):
    conn = psycopg2.connect(**DB_CONFIG)

    create_region_log_table(conn)
    create_region_table(conn)

    print("Téléchargement des régions")
    last_year = get_last_region_year(conn)
    download_all_regions(conn, start_year=last_year + 1)
    
    print("Chargement des fichiers")

    for file in DATA_REGIONS.iterdir():

        if file.suffix.lower() not in [".csv", ".xls", ".xlsx"]:
            continue

        region = extract_region_from_filename(file.name)
        year = int(re.search(r"(\d{4})", file.name).group(1))

        if already_ingested_region(conn, region, year):
            file.unlink()
            continue

        print("Ingestion :", file.name)

        df = _load_single_file(file)
        df["region"] = region
        df = clean_region_dataframe(df)

        insert_dataframe(conn, df)

        log_region_year(conn, region, year)

        file.unlink()
        print("Supprimé :", file.name)

    conn.close()
    print("INGESTION RÉGIONS TERMINÉE")
