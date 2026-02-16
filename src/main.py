from data.weather_loader import fetch_weather

from features.features import create_features
from features.weather_features import *

from modeling.train import train_models
from modeling.evaluate import evaluate_model

from ingestion.downloader import download_and_extract
from ingestion.download_live_data import download_and_extract_live, delete_live_files

from db.ingestion_postgre import ingest_postgres
from db.ingestion_clean_data import ingest_features
from db.ingestion_weather import ingest_weather, ingest_weather_live 
from db.ingestion_conso_meteo_sql import ingest_conso_meteo
from db.ingestion_live import ingest_live_postgres
from db.ingestion_aggregated_live import ingest_live_into_conso_clean
from db.ingestion_regions_clean import ingest_region_clean
from db.ingestion_regions_ecodata import ingest_regions
from data.db_loader import load_from_postgres

from sklearn.model_selection import train_test_split
import mlflow

import joblib
import os
import pandas as pd


DATA_DIR = "../data"
TARGET = "consommation"

ingest_regions()
ingest_region_clean()



df = load_from_postgres()

df = create_features(df)

df[TARGET] = pd.to_numeric(df[TARGET], errors="coerce")

X = df.drop(columns=[TARGET])
y = df[TARGET]

X = X.fillna(0)
y = y.fillna(0)

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)


models = train_models(X_train, y_train)

best_name, best_model, best_r2 = None, None, -999
for name, model in models.items():
    metrics = evaluate_model(model, X_test, y_test)
    print(f"Modèle : {name}")
    for k, v in metrics.items():
        print(f"{k} : {v:.4f}")

    if metrics["R2"] > best_r2:
        best_r2 = metrics["R2"]
        best_name, best_model = name, model

os.makedirs("./src/models", exist_ok=True)
joblib.dump(best_model, "./src/models/model.joblib")


fetch_weather("2020-01-01", "2020-12-31")


print(f"Modèle retenu : {best_name} (R2={best_r2:.4f})")


