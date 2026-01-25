# Import necessary libraries
import pandas as pd
import numpy as np
from pathlib import Path
import unicodedata
import re
import psycopg2

# Constants
DATA_DIR = "./data"
NEW_COLUMNS = [
    "Périmètre", "Nature", "Date", "Heures", "Consommation", "Prévision_J_1", "Prévision_J",
    "Fioul", "Charbon", "Gaz", "Nucléaire", "Eolien", "Solaire", "Hydraulique", "Pompage",
    "Bioénergies", "Ech_physiques", "Taux_de_Co2", "Ech_comm_Angleterre", "Ech_comm_Espagne",
    "Ech_comm_Italie", "Ech_comm_Suisse", "Ech_comm_Allemagne_Belgique", "Fioul_TAC",
    "Fioul_Cogén", "Fioul_Autres", "Gaz_TAC", "Gaz_Cogén", "Gaz_CCG", "Gaz_Autres",
    "Hydraulique_Fil_de_leau_Eclusée", "Hydraulique_Lacs", "Hydraulique_STEP_turbinage",
    "Bioénergies_Déchets", "Bioénergies_Biomasse", "Bioénergies_Biogaz", "Stockage_batterie",
    "Déstockage_batterie", "Eolien_terrestre", "Eolien_offshore"
]
SUPPORTED_EXTENSIONS = [".csv", ".xls", ".xlsx"]

# Database credentials
DB_CONFIG = {
    "host": "edf_postgresl",
    "database": "postgres",
    "user": "postgres",
    "password": "postgres",
    "port": 5432
}
TABLE_NAME = "edf_energy_data"

# Function to clean column names
def clean_colname(col: str) -> str:
    if not isinstance(col, str):
        col = str(col)
    col = col.strip().replace("�", "e").replace("?", "e")
    col = unicodedata.normalize("NFKD", col).encode("ascii", "ignore").decode("ascii")
    col = col.lower()
    col = re.sub(r"[^a-z0-9]+", "_", col)
    col = re.sub(r"_+", "_", col).strip("_")
    return col

# Function to load a single file
def load_single_file(filepath: Path) -> pd.DataFrame:
    suffix = filepath.suffix.lower()

    def read_csv_smart(path):
        best_df = None
        best_cols = 0
        for sep in [";", ",", "\t"]:
            try:
                df_try = pd.read_csv(
                    path, sep=sep, encoding="latin1", low_memory=False, dtype=str, index_col=False
                )
                if df_try.shape[1] > best_cols:
                    best_cols = df_try.shape[1]
                    best_df = df_try
            except Exception:
                continue
        if best_df is None or best_cols == 1:
            raise ValueError("Impossible de détecter le séparateur CSV")
        return best_df

    try:
        if suffix in [".csv", ".xls", ".xlsx"]:
            df = read_csv_smart(filepath)
        else:
            raise ValueError(f"Unsupported file format: {suffix}")
    except Exception as e:
        raise RuntimeError(f"Error loading {filepath.name}: {e}")

    # Clean column names
    df.columns = [clean_colname(c) for c in df.columns]
    df["source_file"] = filepath.name
    return df

# Function to load all data from a directory
def load_all_data(data_dir: str) -> pd.DataFrame:
    data_path = Path(data_dir)
    if not data_path.exists():
        raise FileNotFoundError(f"Directory not found: {data_dir}")

    all_dfs = []
    for file in data_path.iterdir():
        if file.suffix.lower() in SUPPORTED_EXTENSIONS:
            print(f"Loading: {file.name}")
            df = load_single_file(file)
            all_dfs.append(df)

    if not all_dfs:
        return pd.DataFrame()

    return pd.concat(all_dfs, ignore_index=True)

# Function to handle column mismatch
def handle_column_mismatch(df: pd.DataFrame, new_columns: list) -> pd.DataFrame:
    if len(df.columns) < len(new_columns):
        print(f"Column count mismatch: File has {len(df.columns)} columns, but {len(new_columns)} are expected.")
        print("Adding missing columns with None values...")
        for missing_col in new_columns[len(df.columns):]:
            df[missing_col] = None
    elif len(df.columns) > len(new_columns):
        print(f"Column count mismatch: File has {len(df.columns)} columns, but {len(new_columns)} are expected.")
        print("Truncating extra columns...")
        df = df.iloc[:, :len(new_columns)]

    if len(df.columns) != len(new_columns):
        raise ValueError(f"Final column count mismatch: DataFrame has {len(df.columns)} columns, but {len(new_columns)} are expected.")

    df.columns = [col.strip().replace(" ", "_").replace("-", "_").replace("?", "e").lower() for col in new_columns]
    return df

# Function to analyze and cast DataFrame columns to correct data types
def cast_dataframe_columns(df: pd.DataFrame) -> pd.DataFrame:
    data_types = {
        "périmètre": "str",
        "nature": "str",
        "date": "str",
        "heures": "str",
        "consommation": "Int64",
        "prévision_j_1": "Int64",
        "prévision_j": "Int64",
        "fioul": "Int64",
        "charbon": "Int64",
        "gaz": "Int64",
        "nucléaire": "Int64",
        "eolien": "Int64",
        "solaire": "Int64",
        "hydraulique": "Int64",
        "pompage": "Int64",
        "bioénergies": "Int64",
        "ech_physiques": "Int64",
        "taux_de_co2": "Int64",
        "ech_comm_angleterre": "Int64",
        "ech_comm_espagne": "Int64",
        "ech_comm_italie": "Int64",
        "ech_comm_suisse": "Int64",
        "ech_comm_allemagne_belgique": "Int64",
        "fioul_tac": "Int64",
        "fioul_cogén": "Int64",
        "fioul_autres": "Int64",
        "gaz_tac": "Int64",
        "gaz_cogén": "Int64",
        "gaz_ccg": "Int64",
        "gaz_autres": "Int64",
        "hydraulique_fil_de_leau_eclusée": "Int64",
        "hydraulique_lacs": "Int64",
        "hydraulique_step_turbinage": "Int64",
        "bioénergies_déchets": "Int64",
        "bioénergies_biomasse": "Int64",
        "bioénergies_biogaz": "Int64",
        "stockage_batterie": "str",
        "déstockage_batterie": "Int64",
        "eolien_terrestre": "Int64",
        "eolien_offshore": "Int64"
    }
    for col, dtype in data_types.items():
        if dtype == "str":
            df[col] = df[col].astype(str)
        elif dtype == "Int64":
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    return df

# Function to create the table in PostgreSQL
def create_table(conn, table_name):
    curs = conn.cursor()
    curs.execute(f'''
        CREATE TABLE IF NOT EXISTS {table_name} (
            périmètre TEXT,
            nature TEXT,
            date TEXT,
            heures TEXT,
            consommation INTEGER,
            prévision_j_1 INTEGER,
            prévision_j INTEGER,
            fioul INTEGER,
            charbon INTEGER,
            gaz INTEGER,
            nucléaire INTEGER,
            eolien INTEGER,
            solaire INTEGER,
            hydraulique INTEGER,
            pompage INTEGER,
            bioénergies INTEGER,
            ech_physiques INTEGER,
            taux_de_co2 INTEGER,
            ech_comm_angleterre INTEGER,
            ech_comm_espagne INTEGER,
            ech_comm_italie INTEGER,
            ech_comm_suisse INTEGER,
            ech_comm_allemagne_belgique INTEGER,
            fioul_tac INTEGER,
            fioul_cogén INTEGER,
            fioul_autres INTEGER,
            gaz_tac INTEGER,
            gaz_cogén INTEGER,
            gaz_ccg INTEGER,
            gaz_autres INTEGER,
            hydraulique_fil_de_leau_eclusée INTEGER,
            hydraulique_lacs INTEGER,
            hydraulique_step_turbinage INTEGER,
            bioénergies_déchets INTEGER,
            bioénergies_biomasse INTEGER,
            bioénergies_biogaz INTEGER,
            stockage_batterie TEXT,
            déstockage_batterie INTEGER,
            eolien_terrestre INTEGER,
            eolien_offshore INTEGER
        )
    ''')
    conn.commit()

# Function to insert data into PostgreSQL
def insert_data_from_df(conn, table_name, df):
    curs = conn.cursor()
    for _, row in df.iterrows():
        # Replace NAType with None
        row = row.where(pd.notnull(row), None)
        
        db_id = f"{row['périmètre']}_{row['date']}_{row['heures']}"
        curs.execute(f"SELECT * FROM {table_name} WHERE périmètre=%s AND date=%s AND heures=%s", 
                     (row['périmètre'], row['date'], row['heures']))
        if not curs.fetchone():
            try:
                curs.execute(f'''
                    INSERT INTO {table_name} VALUES ({','.join(['%s'] * len(row))})
                ''', tuple(row))
                conn.commit()
            except Exception as e:
                print(f"Error inserting data: {db_id}. Error: {e}")
        else:
            print(f"Exists: {db_id}")

# Main function to execute the workflow
def main():
    # Load data
    df = load_all_data(DATA_DIR)
    df = handle_column_mismatch(df, NEW_COLUMNS)
    df = cast_dataframe_columns(df)

    # Connect to PostgreSQL
    conn = psycopg2.connect(**DB_CONFIG)

    # Create table and insert data
    create_table(conn, TABLE_NAME)
    insert_data_from_df(conn, TABLE_NAME, df)

    # Close connection
    conn.close()

if __name__ == "__main__":
    main()