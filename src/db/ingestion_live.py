import psycopg2
import hashlib
from pathlib import Path
import pandas as pd

# On réutilise TON downloader live
from ingestion.download_live_data import delete_live_files, download_and_extract_live
from data.data_loader import _load_single_file


# ================================
# CONFIG
# ================================
DB_CONFIG = {
    "host": "localhost",
    "database": "postgres",
    "user": "postgres",
    "password": "postgres",
    "port": 5441,
}

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"

TARGET_EXT = [".csv", ".xls", ".xlsx"]

TABLE_DATA = "eco2mix_live_raw"
TABLE_LOG  = "eco2mix_live_files"


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

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_LOG} (
            filename TEXT PRIMARY KEY,
            checksum TEXT,
            ingested_at TIMESTAMP DEFAULT NOW()
        );
    """)

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


def make_datetime(df):
    return pd.to_datetime(df["date"] + " " + df["heures"], errors="coerce")

def get_last_timestamp(conn):
    cur = conn.cursor()
    cur.execute(f"SELECT MAX(date || ' ' || heures) FROM {TABLE_DATA}")
    last = cur.fetchone()[0]
    cur.close()
    return pd.to_datetime(last) if last else None

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # normalisation des valeurs invalides
    df = df.replace(["ND", "None", "nan", ""], pd.NA)

    # Normalisation des noms de colonnes foireux
    df = df.rename(columns=COLUMN_RENAME)
    df = df.reindex(columns=EXPECTED_COLS)

    for col in df.columns:
        converted = pd.to_numeric(df[col], errors="coerce")
        ratio_numeric = converted.notna().mean()

        if ratio_numeric > 0.3:
            df[col] = converted
        else:
            df[col] = df[col].astype("string")
            df[col] = df[col].where(df[col].notna(), None)

    # Garder uniquement les lignes avec une consommation non nulle
    df = df[df["consommation"].notna()]

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



def ingest_live_postgres():
    print("Téléchargement du fichier live")
    extracted = download_and_extract_live()

    if not extracted:
        print("Aucun fichier live")
        return

    file = extracted[0]

    print("Connexion PostgreSQL")
    conn = psycopg2.connect(**DB_CONFIG)
    create_tables(conn)

    print("Chargement CSV")
    df = _load_single_file(file)
    df = clean_dataframe(df)

    df = df[df["consommation"].notna()]

    # Création du timestamp métier
    df["dt"] = pd.to_datetime(df["date"] + " " + df["heures"], errors="coerce")

    # Dernière date en base
    cur = conn.cursor()
    cur.execute(f"SELECT MAX(date || ' ' || heures) FROM {TABLE_DATA}")
    last = cur.fetchone()[0]
    cur.close()
    
    delete_live_files()

    if last:
        last_dt = pd.to_datetime(last)
        df = df[df["dt"] > last_dt]

    if df.empty:
        print("Aucune nouvelle ligne à insérer")
        conn.close()
        return

    print(f"{len(df)} nouvelles lignes")

    # On enlève la colonne technique
    df = df.drop(columns=["dt"])

    insert_dataframe(conn, df)
    conn.close()

    print("LIVE INGESTION OK")
