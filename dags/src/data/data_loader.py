import pandas as pd
import re
import unicodedata
from pathlib import Path


SUPPORTED_EXTENSIONS = [".csv", ".xls", ".xlsx"]

def _clean_colname(col: str) -> str:
    if not isinstance(col, str):
        col = str(col)

    col = col.strip()
    col = col.replace("�", "e").replace("?", "e")

    col = unicodedata.normalize("NFKD", col)
    col = col.encode("ascii", "ignore").decode("ascii")

    col = col.lower()
    col = re.sub(r"[^a-z0-9]+", "_", col)
    col = re.sub(r"_+", "_", col).strip("_")

    return col


def _load_single_file(filepath: Path) -> pd.DataFrame:
    suffix = filepath.suffix.lower()

    def read_csv_smart(path):
        best_df = None
        best_cols = 0

        for sep in [";", ",", "\t"]:
            try:
                df_try = pd.read_csv(
                    path,
                    sep=sep,
                    encoding="latin1",
                    low_memory=False,
                    dtype=str,
                    index_col=False
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
        if suffix == ".xls":
                df = read_csv_smart(filepath)
    except Exception as e:
        raise RuntimeError(f"Erreur lors du chargement de {filepath.name} : {e}")

    # Nettoyage des colonnes
    df.columns = [_clean_colname(c) for c in df.columns]
    
    df["source_file"] = filepath.name

    return df




def load_all_data(data_dir: str) -> pd.DataFrame:
    """
    Charge automatiquement tous les fichiers du dossier data/
    """
    data_path = Path(data_dir)

    if not data_path.exists():
        raise FileNotFoundError(f"Dossier introuvable : {data_dir}")

    all_dfs = []

    for file in data_path.iterdir():
        if file.suffix.lower() in SUPPORTED_EXTENSIONS:
            print(f"Chargement : {file.name}")
            df = _load_single_file(file)
            all_dfs.append(df)

    if not all_dfs:
        return pd.DataFrame()

    df_final = pd.concat(all_dfs, ignore_index=True)
    return df_final