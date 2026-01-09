import pandas as pd

def create_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # features
    if "date" in df.columns:
        df["day"] = df["date"].dt.day
        df["month"] = df["date"].dt.month
        df["dayofweek"] = df["date"].dt.dayofweek
        df["weekend"] = df["dayofweek"].isin([5, 6]).astype(int)

    drop_cols = [
        "perimetre",
        "nature",
        "source_file",
        "date",
    ]
    df.drop(columns=[c for c in drop_cols if c in df.columns], inplace=True)

    # Forcer toutes les colonnes en numérique 
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # valeurs manquantes
    df = df.fillna(0)

    # garder uniquement les lignes avec consommation
    if "consommation" in df.columns:
        df = df[df["consommation"] > 0]

    return df
