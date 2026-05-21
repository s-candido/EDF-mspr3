"""
Per-region consumption prediction pipeline (Airflow-adapted).

Builds per-region feature tables (agg_conso_meteo_features_{region}),
trains per-region models, runs batch predictions, and aggregates
to national totals via mean of per-city predictions.

Adapted from src/pipelines/prediction_consommation_regions.py for
Airflow Docker runtime with Docker service hostnames.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

JsonDict = dict[str, Any]

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
import psycopg2
from mlflow.tracking import MlflowClient
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsRegressor

from src.db.city_region_mapping import (
    all_regions,
    build_region_feature_table,
    create_city_region_mapping_table,
    get_cities_for_region,
    normalize_region_name,
)

DB_CONFIG = {
    "host": "edf_postgresql",
    "database": "postgres",
    "user": "postgres",
    "password": "postgres",
    "port": 5432,
}

MLFLOW_URL = "http://mlflow:5000"
MLFLOW_EXPERIMENT = "EDF_Region_Model_Experiment"

FEATURE_COLUMNS = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "snowfall",
    "weather_code",
    "hour",
    "month",
    "dayofweek",
    "weekend",
]

TARGET = "consommation"
MLFLOW_MODEL_PREFIX = "MODEL_EDF_REGION"


def build_all_region_feature_tables(
    db_config: dict | None = None,
    regions: list[str] | None = None,
    replace: bool = False,
) -> dict[str, str]:
    cfg = db_config or DB_CONFIG
    if regions is None:
        regions = all_regions()

    conn = psycopg2.connect(**cfg)
    try:
        create_city_region_mapping_table(conn)
        result = {}
        for region in regions:
            print(f"[{region}] Building feature table ...")
            table_name = build_region_feature_table(conn, region, replace=replace)
            result[region] = table_name
            print(f"[{region}] -> {table_name}")
    finally:
        conn.close()
    return result


def _mape(y_true, y_pred):
    eps = 1e-9
    return float(np.mean(np.abs((y_true - y_pred) / (np.abs(y_true) + eps))) * 100)


def _train_models(X, y):
    models = {
        "LinearRegression": LinearRegression(),
        "RandomForest": RandomForestRegressor(
            n_estimators=200, random_state=42, n_jobs=-1
        ),
        "KNN": KNeighborsRegressor(n_neighbors=7),
    }
    trained = {}
    for name, model in models.items():
        model.fit(X, y)
        trained[name] = model
    return trained


def _evaluate_model(model, X_test, y_test):
    y_pred = model.predict(X_test)
    return {
        "R2": float(r2_score(y_test, y_pred)),
        "RMSE": float(np.sqrt(mean_squared_error(y_test, y_pred))),
        "MAPE": _mape(y_test, y_pred),
    }


def train_region_model(
    region: str,
    feature_table: str,
    db_config: dict | None = None,
    mlflow_url: str | None = None,
    feature_columns: list[str] | None = None,
    target: str = TARGET,
    test_size: float = 0.2,
) -> dict:
    cfg = db_config or DB_CONFIG
    tracking_uri = mlflow_url or MLFLOW_URL
    cols = feature_columns or FEATURE_COLUMNS
    model_name = f"{MLFLOW_MODEL_PREFIX}_{normalize_region_name(region)}"

    conn = psycopg2.connect(**cfg)
    try:
        print(f"[{region}] Loading data from {feature_table} ...")
        df = pd.read_sql_query(f"SELECT * FROM {feature_table}", conn)
    finally:
        conn.close()

    if df.empty:
        print(f"[{region}] No data - skipping training.")
        return {"region": region, "status": "skipped", "reason": "no data"}

    df[target] = pd.to_numeric(df[target], errors="coerce")
    X = df[cols].fillna(0)
    y = df[target].fillna(0)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=42
    )

    models = _train_models(X_train, y_train)
    best_name, best_model, best_r2 = None, None, -999

    for name, model in models.items():
        metrics = _evaluate_model(model, X_test, y_test)
        print(
            f"[{region}] {name}: R2={metrics['R2']:.4f}, "
            f"RMSE={metrics['RMSE']:.2f}, MAPE={metrics['MAPE']:.2f}%"
        )
        if metrics["R2"] > best_r2:
            best_r2 = metrics["R2"]
            best_name, best_model = name, model

    print(f"[{region}] Best: {best_name} (R2={best_r2:.4f})")

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(MLFLOW_EXPERIMENT)

    with mlflow.start_run(
        run_name=f"{region}_{best_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    ):
        mlflow.log_param("region", region)
        mlflow.log_param("model_type", best_name)
        mlflow.log_param("n_samples", len(X_train))
        mlflow.log_param("n_features", len(cols))
        mlflow.log_param("feature_columns", str(cols))

        metrics = _evaluate_model(best_model, X_test, y_test)
        mlflow.log_metric("R2", metrics["R2"])
        mlflow.log_metric("RMSE", metrics["RMSE"])
        mlflow.log_metric("MAPE", metrics["MAPE"])

        mlflow.sklearn.log_model(best_model, artifact_path=model_name)
        model_uri = f"runs:/{mlflow.active_run().info.run_id}/{model_name}"
        mlflow.register_model(model_uri, model_name)

    return {
        "region": region,
        "status": "success",
        "best_model": best_name,
        "R2": best_r2,
        "n_samples": len(X_train),
    }


def train_all_region_models(
    feature_tables: dict[str, str],
    db_config: dict | None = None,
    mlflow_url: str | None = None,
    feature_columns: list[str] | None = None,
) -> list[dict]:
    results = []
    for region, table_name in feature_tables.items():
        result = train_region_model(
            region=region,
            feature_table=table_name,
            db_config=db_config,
            mlflow_url=mlflow_url,
            feature_columns=feature_columns,
        )
        results.append(result)
    return results


def _get_latest_model_version(model_name: str, mlflow_url: str) -> int | None:
    mlflow.set_tracking_uri(mlflow_url)
    try:
        client = MlflowClient()
        versions = client.get_latest_versions(
            model_name, stages=["None", "Staging", "Production"]
        )
        if versions:
            return max(int(v.version) for v in versions)
    except Exception:
        pass
    return None


def predict_region(
    region: str,
    feature_table: str,
    db_config: dict,
    mlflow_url: str,
    feature_columns: list[str],
    selected_years: list[int] | None = None,
    selected_months: list[int] | None = None,
    selected_days: list[int] | None = None,
) -> pd.DataFrame:
    model_name = f"{MLFLOW_MODEL_PREFIX}_{normalize_region_name(region)}"
    mlflow.set_tracking_uri(mlflow_url)

    version = _get_latest_model_version(model_name, mlflow_url)
    if version is None:
        print(f"[{region}] No model found for '{model_name}' - skipping.")
        return pd.DataFrame()

    model_uri = f"models:/{model_name}/{version}"
    model = mlflow.pyfunc.load_model(model_uri)

    conn = psycopg2.connect(**db_config)
    try:
        query = f"SELECT * FROM {feature_table}"
        conditions = []
        if selected_years:
            years_str = ",".join(str(y) for y in selected_years)
            conditions.append(f"year IN ({years_str})")
        if selected_months:
            months_str = ",".join(str(m) for m in selected_months)
            conditions.append(f"month IN ({months_str})")
        if selected_days:
            days_str = ",".join(str(d) for d in selected_days)
            conditions.append(f"day IN ({days_str})")
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY datetime, city"

        df = pd.read_sql_query(query, conn)
    finally:
        conn.close()

    if df.empty:
        print(f"[{region}] No data matching filters.")
        return df

    X = df[feature_columns].fillna(0)
    predictions = model.predict(X)

    result_df = pd.DataFrame(
        {
            "city": df["city"],
            "region": region,
            "datetime": df["datetime"],
            "prediction": predictions,
            "consommation_reelle": df.get(TARGET, None),
        }
    )
    for col in feature_columns:
        result_df[col] = df[col].values

    return result_df


def predict_all_regions(
    feature_tables: dict[str, str],
    db_config: dict | None = None,
    mlflow_url: str | None = None,
    feature_columns: list[str] | None = None,
    selected_years: list[int] | None = None,
    selected_months: list[int] | None = None,
    selected_days: list[int] | None = None,
    prediction_table_prefix: str = "batch_predictions",
) -> dict:
    cfg = db_config or DB_CONFIG
    tracking_uri = mlflow_url or MLFLOW_URL
    cols = feature_columns or FEATURE_COLUMNS

    years_str = "_".join(str(y) for y in (selected_years or ["all"]))
    months_str = "_".join(str(m) for m in (selected_months or ["all"]))
    days_str = "_".join(str(d) for d in (selected_days or ["all"]))

    all_pred_cities = []
    for reg in feature_tables:
        all_pred_cities.extend(get_cities_for_region(reg))
    unique_cities = sorted(set(all_pred_cities))
    cities_part = "_".join(unique_cities) if len(unique_cities) <= 6 else "all_regions"

    prediction_table = (
        f"{prediction_table_prefix}_{years_str}_{months_str}_{days_str}_{cities_part}"
    )

    all_predictions = []

    for region, table_name in feature_tables.items():
        print(f"[{region}] Predicting ...")
        df_pred = predict_region(
            region=region,
            feature_table=table_name,
            db_config=cfg,
            mlflow_url=tracking_uri,
            feature_columns=cols,
            selected_years=selected_years,
            selected_months=selected_months,
            selected_days=selected_days,
        )
        if not df_pred.empty:
            all_predictions.append(df_pred)
            print(f"[{region}] -> {len(df_pred)} predictions")

    if not all_predictions:
        print("No predictions generated.")
        return {"status": "error", "reason": "no predictions"}

    combined = pd.concat(all_predictions, ignore_index=True)

    conn = psycopg2.connect(**cfg)
    try:
        from psycopg2.extras import execute_values

        with conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {prediction_table} (
                    id BIGSERIAL PRIMARY KEY,
                    city TEXT,
                    region TEXT,
                    datetime TIMESTAMP,
                    prediction DOUBLE PRECISION,
                    consommation_reelle DOUBLE PRECISION,
                    temperature_2m DOUBLE PRECISION,
                    relative_humidity_2m DOUBLE PRECISION,
                    precipitation DOUBLE PRECISION,
                    snowfall DOUBLE PRECISION,
                    weather_code INTEGER,
                    hour INTEGER,
                    month INTEGER,
                    dayofweek INTEGER,
                    weekend INTEGER
                );
            """
            )
        conn.commit()

        cols_db = [
            "city",
            "region",
            "datetime",
            "prediction",
            "consommation_reelle",
            "temperature_2m",
            "relative_humidity_2m",
            "precipitation",
            "snowfall",
            "weather_code",
            "hour",
            "month",
            "dayofweek",
            "weekend",
        ]
        insert_cols = ", ".join(cols_db)
        values = (
            combined[cols_db].where(pd.notnull(combined[cols_db]), None).values.tolist()
        )

        with conn.cursor() as cursor:
            execute_values(
                cursor,
                f"INSERT INTO {prediction_table} ({insert_cols}) VALUES %s",
                values,
            )
        conn.commit()
    finally:
        conn.close()

    region_agg = (
        combined.groupby(["region", "datetime"])
        .agg({"prediction": "mean", "consommation_reelle": "mean"})
        .reset_index()
    )

    national_agg = (
        region_agg.groupby("datetime")
        .agg({"prediction": "sum", "consommation_reelle": "sum"})
        .reset_index()
    )

    print(f"\n{'='*60}")
    print(f"Predictions stored in: {prediction_table}")
    print(f"Total rows: {len(combined)}")
    print(f"\nPer-region average predicted consumption:")
    for region in sorted(region_agg["region"].unique()):
        r_data = region_agg[region_agg["region"] == region]
        print(f"  {region}: {r_data['prediction'].mean():.0f} kWh (avg)")
    print(f"\nNational average consumption:")
    print(f"  Predicted: {national_agg['prediction'].mean():.0f} kWh")
    print(f"  Actual:    {national_agg['consommation_reelle'].mean():.0f} kWh")
    print(f"{'='*60}")

    return {
        "status": "success",
        "prediction_table": prediction_table,
        "n_rows": len(combined),
        "n_regions": len(combined["region"].unique()),
        "national_avg_predicted": float(national_agg["prediction"].mean()),
        "national_avg_actual": float(national_agg["consommation_reelle"].mean()),
    }


def run_pipeline_prediction_consomation_regions(
    db_config: dict | None = None,
    mlflow_url: str | None = None,
    feature_columns: list[str] | None = None,
    regions: list[str] | None = None,
    rebuild_features: bool = False,
    skip_training: bool = False,
    skip_prediction: bool = False,
    selected_years: list[int] | None = None,
    selected_months: list[int] | None = None,
    selected_days: list[int] | None = None,
) -> dict:
    """
    Orchestrate the complete per-region consumption prediction pipeline.

    Pipeline phases:
        1. Build per-region feature tables (agg_conso_meteo_features_{region})
        2. Train per-region models (logged to MLflow as MODEL_EDF_REGION_{region})
        3. Batch predict per region -> store in batch_predictions_{years}_{months}_{days}_{cities}
    """
    print("=" * 60)
    print("PIPELINE: Prediction Consommation Regions")
    print("=" * 60)

    if regions is None:
        regions = all_regions()

    cfg = db_config or DB_CONFIG
    tracking_uri = mlflow_url or MLFLOW_URL
    cols = feature_columns or FEATURE_COLUMNS

    # Phase 1: Feature tables
    print("\n[Phase 1] Building per-region feature tables ...")
    feature_tables = build_all_region_feature_tables(
        db_config=cfg, regions=regions, replace=rebuild_features
    )
    print(f"  {len(feature_tables)} tables created.\n")

    # Phase 2: Training
    training_results = []
    if not skip_training:
        print("[Phase 2] Training per-region models ...")
        training_results = train_all_region_models(
            feature_tables=feature_tables,
            db_config=cfg,
            mlflow_url=tracking_uri,
            feature_columns=cols,
        )
        n_trained = sum(1 for r in training_results if r.get("status") == "success")
        n_skipped = sum(1 for r in training_results if r.get("status") == "skipped")
        print(f"  {n_trained} trained, {n_skipped} skipped ({len(regions)} total).\n")
    else:
        print("[Phase 2] Training skipped.\n")

    # Phase 3: Prediction
    prediction_results = {}
    if not skip_prediction:
        print("[Phase 3] Running batch predictions ...")
        prediction_results = predict_all_regions(
            feature_tables=feature_tables,
            db_config=cfg,
            mlflow_url=tracking_uri,
            feature_columns=cols,
            selected_years=selected_years,
            selected_months=selected_months,
            selected_days=selected_days,
        )
    else:
        print("[Phase 3] Prediction skipped.\n")

    print("Pipeline complete.")
    return {
        "feature_tables": feature_tables,
        "training_results": training_results,
        "prediction_results": prediction_results,
    }
