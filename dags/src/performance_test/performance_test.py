import numpy as np
import pandas as pd
import psycopg2
import mlflow
from mlflow.pyfunc import load_model
from mlflow.tracking import MlflowClient
import matplotlib.pyplot as plt
import tempfile
import io

from src.modeling.evaluate import evaluate_model

MLFLOW_URL = "http://mlflow:5000"
MODEL_NAME = "MODEL_EDF"
TARGET = "consommation"

DB_CONFIG = {
    "host": "edf_postgresql",
    "database": "postgres",
    "user": "postgres",
    "password": "postgres",
    "port": 5432,
}

FEATURE_COLUMNS = [
    "temp_fr", "snow_fr", "hour", "month", "dayofweek", "weekend",
    "consommation",
]


def _execute_query(query: str, params: tuple = None) -> pd.DataFrame:
    """Execute a PostgreSQL query and return results as a DataFrame."""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        df = pd.read_sql(query, conn, params=params)
    finally:
        conn.close()
    return df


def check_data_availability(
    years: list,
    months: list,
    days: list = None,
) -> dict:
    """
    Check if feature data exists in the database for the given time filters.

    Checks in order:
    1. `agg_conso_meteo_features` (primary feature table)
    2. `aggregated_conso_weather` (fallback raw aggregation table)

    Args:
        years: List of years to check.
        months: List of months to check.
        days: Optional list of days to filter on.

    Returns:
        dict with keys:
            - 'source': 'agg_conso_meteo_features', 'aggregated_conso_weather', or None
            - 'row_count': number of matching rows found
            - 'years': years that were checked
            - 'months': months that were checked
    """
    year_placeholders = ",".join(["%s"] * len(years))
    month_placeholders = ",".join(["%s"] * len(months))

    params = list(years) + list(months)

    day_filter = ""
    if days:
        day_placeholders = ",".join(["%s"] * len(days))
        day_filter = f" AND day IN ({day_placeholders})"
        params.extend(days)

    # --- Primary: agg_conso_meteo_features ---
    query = f"""
        SELECT COUNT(*) AS cnt
        FROM agg_conso_meteo_features
        WHERE year IN ({year_placeholders})
          AND month IN ({month_placeholders})
          {day_filter}
    """
    try:
        result = _execute_query(query, tuple(params))
        cnt = int(result.iloc[0]["cnt"])
        if cnt > 0:
            print(f"Found {cnt} rows in agg_conso_meteo_features for years={years}, months={months}"
                  + (f", days={days}" if days else ""))
            return {"source": "agg_conso_meteo_features", "row_count": cnt, "years": years, "months": months}
    except Exception as e:
        print(f"agg_conso_meteo_features not available: {e}")

    # --- Fallback: aggregated_conso_weather ---
    try:
        result = _execute_query(query.replace("agg_conso_meteo_features", "aggregated_conso_weather"), tuple(params))
        cnt = int(result.iloc[0]["cnt"])
        if cnt > 0:
            print(f"Found {cnt} rows in aggregated_conso_weather for years={years}, months={months}"
                  + (f", days={days}" if days else ""))
            return {"source": "aggregated_conso_weather", "row_count": cnt, "years": years, "months": months}
    except Exception as e:
        print(f"aggregated_conso_weather not available: {e}")

    print(f"TODO NO DATA HERE / TRIGGER DATA INGESTION DAG for years={years}, months={months}"
          + (f", days={days}" if days else ""))
    return {"source": None, "row_count": 0, "years": years, "months": months}


def load_test_data(
    years: list,
    months: list,
    days: list = None,
) -> pd.DataFrame:
    """
    Load test data from the best available source.

    Priority:
    1. `agg_conso_meteo_features` (has pre-computed features)
    2. `aggregated_conso_weather` (raw aggregated data)

    Raises ValueError if no data is found in either table.

    Args:
        years: List of years to load.
        months: List of months to load.
        days: Optional list of days to filter on.

    Returns:
        DataFrame with feature columns and consommation target.
    """
    availability = check_data_availability(years, months, days)
    source = availability["source"]

    if source is None:
        raise ValueError(
            f"No data found for years={years}, months={months}"
            + (f", days={days}" if days else "")
            + ". Trigger the Data Ingestion DAG first."
        )

    year_placeholders = ",".join(["%s"] * len(years))
    month_placeholders = ",".join(["%s"] * len(months))
    params = list(years) + list(months)

    day_filter = ""
    if days:
        day_placeholders = ",".join(["%s"] * len(days))
        day_filter = f" AND day IN ({day_placeholders})"
        params.extend(days)

    if source == "agg_conso_meteo_features":
        cols = ", ".join(FEATURE_COLUMNS)
        query = f"""
            SELECT {cols}
            FROM agg_conso_meteo_features
            WHERE year IN ({year_placeholders})
              AND month IN ({month_placeholders})
              {day_filter}
            ORDER BY datetime
        """
    else:
        # aggregated_conso_weather - select equivalent columns
        query = f"""
            SELECT *
            FROM aggregated_conso_weather
            WHERE year IN ({year_placeholders})
              AND month IN ({month_placeholders})
              {day_filter}
            ORDER BY datetime
        """

    print(f"Loading test data from {source} for years={years}, months={months}"
          + (f", days={days}" if days else ""))
    df = _execute_query(query, tuple(params))
    print(f"Loaded {len(df)} rows from {source}")
    return df


def get_latest_model_version(model_name: str) -> int:
    """
    Get the latest version of a model from the MLflow model registry.

    Args:
        model_name: The name of the model in the MLflow model registry.

    Returns:
        The latest version of the model, or None if not found.
    """
    try:
        client = MlflowClient()
        versions = client.get_latest_versions(model_name, stages=["None", "Staging", "Production"])
        if versions:
            latest_version = max(int(version.version) for version in versions)
            print(f"Latest version of model '{model_name}' is: {latest_version}")
            return latest_version
        else:
            print(f"No versions found for model '{model_name}'.")
            return None
    except Exception as e:
        print(f"Error fetching latest version: {e}")
        return None


def add_noise_to_features(X: pd.DataFrame, noise_level: float, seed: int = 42) -> pd.DataFrame:
    """
    Add Gaussian noise to numerical features.

    Args:
        X: Input features.
        noise_level: Standard deviation of noise as fraction of feature std.
        seed: Random seed for reproducibility.

    Returns:
        Features with added noise.
    """
    np.random.seed(seed)
    X_noisy = X.copy()

    numeric_cols = X_noisy.select_dtypes(include=[np.number]).columns

    for col in numeric_cols:
        col_std = X_noisy[col].std()
        if col_std > 0:
            noise = np.random.normal(0, noise_level * col_std, size=X_noisy[col].shape)
            X_noisy[col] = X_noisy[col] + noise

    return X_noisy


def run_performance_test(
    test_years: list,
    test_months: list,
    test_days: list = None,
    noise_levels: list = None,
    experiment_name: str = "Performance_Test",
) -> dict:
    """
    Run performance test on latest model with increasing noise levels.

    Pipeline:
    1. Check data availability in agg_conso_meteo_features (primary)
       or aggregated_conso_weather (fallback).
    2. Load test data filtered by year/month/day.
    3. Pull latest model version from MLflow.
    4. Test model with increasing noise levels.
    5. Measure metric degradation and log to MLflow.

    Args:
        test_years: List of years to test.
        test_months: List of months to test.
        test_days: Optional list of days to filter on.
        noise_levels: Noise levels to test (fraction of feature std).
        experiment_name: MLflow experiment name.

    Returns:
        Dictionary with model_version, noise_levels, metrics, baseline,
        degradation, predictions, and mlflow_run_id.
    """
    if noise_levels is None:
        noise_levels = [0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5]

    test_date = f"y{test_years}_m{test_months}" + (f"_d{test_days}" if test_days else "")

    # --- Load test data from DB ---
    df = load_test_data(test_years, test_months, test_days)
    print(f"Loading test data for {test_date}")

    df[TARGET] = pd.to_numeric(df[TARGET], errors="coerce")

    X = df.drop(columns=[TARGET])
    y = df[TARGET]

    X = X.fillna(0)
    y = y.fillna(0)

    X_test = X.head(1000)
    y_test = y.head(1000)

    print(f"Test data shape: X={X_test.shape}, y={y_test.shape}")

    # --- Load model ---
    mlflow.set_tracking_uri(MLFLOW_URL)
    model_version = get_latest_model_version(MODEL_NAME)
    model_uri = f"models:/{MODEL_NAME}/{model_version}"
    print(f"Loading model {MODEL_NAME} version {model_version}")
    model = load_model(model_uri)
    print(f"Model loaded successfully from {model_uri}")

    mlflow.set_experiment(experiment_name + test_date)
    with mlflow.start_run():

        mlflow.log_param("model_version", model_version)
        mlflow.log_param("noise_levels", str(noise_levels))
        mlflow.log_param("test_date", test_date)
        mlflow.log_param("test_years", str(test_years))
        mlflow.log_param("test_months", str(test_months))
        if test_days:
            mlflow.log_param("test_days", str(test_days))

        results = {
            "model_version": model_version,
            "noise_levels": noise_levels,
            "metrics": {
                "R2": [],
                "RMSE": [],
                "MAPE (%)": [],
            },
            "predictions": [],
            "baseline": None,
            "degradation": {
                "R2": [],
                "RMSE": [],
                "MAPE (%)": [],
            },
        }

        print("\nRunning performance tests with increasing noise levels...")
        for i, noise_level in enumerate(noise_levels):
            print(f"\n{'=' * 60}")
            print(f"Test {i + 1}/{len(noise_levels)}: Noise level = {noise_level:.2f}")
            print(f"{'=' * 60}")

            if noise_level > 0:
                X_noisy = add_noise_to_features(X_test, noise_level, seed=i)
            else:
                X_noisy = X_test.copy()

            metrics = evaluate_model(model, X_noisy, y_test)

            results["metrics"]["R2"].append(metrics["R2"])
            results["metrics"]["RMSE"].append(metrics["RMSE"])
            results["metrics"]["MAPE (%)"].append(metrics["MAPE (%)"])

            y_pred = model.predict(X_noisy)
            results["predictions"].append(y_pred)

            print(f"R2: {metrics['R2']:.4f}")
            print(f"RMSE: {metrics['RMSE']:.4f}")
            print(f"MAPE (%): {metrics['MAPE (%)']:.2f}")

            mlflow.log_metric("R2", metrics["R2"])
            mlflow.log_metric("RMSE", metrics["RMSE"])
            mlflow.log_metric("MAPE", metrics["MAPE (%)"])
            mlflow.log_metric("noise_level", noise_level)

            if i == 0:
                results["baseline"] = metrics.copy()

        baseline = results["baseline"]
        print("\nCalculating metric degradation...")
        for i, noise_level in enumerate(noise_levels):
            if noise_level > 0:
                r2_degradation = ((results["metrics"]["R2"][i] - baseline["R2"]) / abs(baseline["R2"])) * 100
                rmse_degradation = ((results["metrics"]["RMSE"][i] - baseline["RMSE"]) / baseline["RMSE"]) * 100
                mape_degradation = ((results["metrics"]["MAPE (%)"][i] - baseline["MAPE (%)"]) / baseline["MAPE (%)"]) * 100
            else:
                r2_degradation = 0.0
                rmse_degradation = 0.0
                mape_degradation = 0.0

            results["degradation"]["R2"].append(r2_degradation)
            results["degradation"]["RMSE"].append(rmse_degradation)
            results["degradation"]["MAPE (%)"].append(mape_degradation)

            mlflow.log_metric(f"R2_noise_{noise_level}", results["metrics"]["R2"][i])
            mlflow.log_metric(f"RMSE_noise_{noise_level}", results["metrics"]["RMSE"][i])
            mlflow.log_metric(f"MAPE_noise_{noise_level}", results["metrics"]["MAPE (%)"][i])
            mlflow.log_metric(f"R2_degradation_{noise_level}", r2_degradation)
            mlflow.log_metric(f"RMSE_degradation_{noise_level}", rmse_degradation)
            mlflow.log_metric(f"MAPE_degradation_{noise_level}", mape_degradation)

        print("\n" + "=" * 60)
        print("PERFORMANCE TEST SUMMARY")
        print("=" * 60)
        print(f"Model Version: {model_version}")
        print(f"Baseline Metrics (noise=0.0):")
        print(f"  R2: {baseline['R2']:.4f}")
        print(f"  RMSE: {baseline['RMSE']:.4f}")
        print(f"  MAPE (%): {baseline['MAPE (%)']:.2f}")

        print("\nMetric Degradation:")
        print(f"{'Noise':<10} {'R2 Deg (%)':<15} {'RMSE Deg (%)':<15} {'MAPE Deg (%)':<15}")
        print("-" * 60)
        for i, noise_level in enumerate(noise_levels):
            print(f"{noise_level:<10.2f} "
                  f"{results['degradation']['R2'][i]:<15.2f} "
                  f"{results['degradation']['RMSE'][i]:<15.2f} "
                  f"{results['degradation']['MAPE (%)'][i]:<15.2f}")

        _generate_and_log_plots(results)

        results["mlflow_run_id"] = mlflow.active_run().info.run_id
        print(f"\nResults logged to MLFlow run ID: {results['mlflow_run_id']}")

    return results


def _generate_and_log_plots(results: dict):
    """
    Generate performance plots and log them to MLFlow as artifacts.

    Args:
        results: Results from run_performance_test.
    """
    noise_levels = results["noise_levels"]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(f'Model Performance vs Noise Level (Version {results["model_version"]})',
                 fontsize=14, fontweight="bold")

    ax1 = axes[0, 0]
    ax1.plot(noise_levels, results["metrics"]["R2"], "o-", label="R2", linewidth=2, markersize=8)
    ax1.set_xlabel("Noise Level (fraction of std)", fontsize=11)
    ax1.set_ylabel("R2 Score", fontsize=11)
    ax1.set_title("Raw Metrics: R2", fontsize=12, fontweight="bold")
    ax1.grid(True, alpha=0.3)
    ax1.legend()

    ax2 = axes[0, 1]
    ax2.plot(noise_levels, results["metrics"]["RMSE"], "s-", label="RMSE",
             color="orange", linewidth=2, markersize=8)
    ax2.set_xlabel("Noise Level (fraction of std)", fontsize=11)
    ax2.set_ylabel("RMSE", fontsize=11)
    ax2.set_title("Raw Metrics: RMSE", fontsize=12, fontweight="bold")
    ax2.grid(True, alpha=0.3)
    ax2.legend()

    ax3 = axes[1, 0]
    ax3.plot(noise_levels, results["metrics"]["MAPE (%)"], "^-", label="MAPE",
             color="green", linewidth=2, markersize=8)
    ax3.set_xlabel("Noise Level (fraction of std)", fontsize=11)
    ax3.set_ylabel("MAPE (%)", fontsize=11)
    ax3.set_title("Raw Metrics: MAPE", fontsize=12, fontweight="bold")
    ax3.grid(True, alpha=0.3)
    ax3.legend()

    ax4 = axes[1, 1]
    ax4.plot(noise_levels, results["degradation"]["R2"], "o-", label="R2 Degradation",
             linewidth=2, markersize=8)
    ax4.plot(noise_levels, results["degradation"]["RMSE"], "s-", label="RMSE Degradation",
             color="orange", linewidth=2, markersize=8)
    ax4.plot(noise_levels, results["degradation"]["MAPE (%)"], "^-", label="MAPE Degradation",
             color="green", linewidth=2, markersize=8)
    ax4.axhline(y=0, color="black", linestyle="--", alpha=0.5)
    ax4.set_xlabel("Noise Level (fraction of std)", fontsize=11)
    ax4.set_ylabel("Degradation (%)", fontsize=11)
    ax4.set_title("Relative Metric Degradation", fontsize=12, fontweight="bold")
    ax4.grid(True, alpha=0.3)
    ax4.legend()

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=300, bbox_inches="tight")
    buf.seek(0)
    plt.close()

    print(f"\nSummary plot logged to MLFlow")

    fig2, ax = plt.subplots(figsize=(10, 6))
    ax.plot(noise_levels, results["degradation"]["R2"], "o-", label="R2 Degradation",
            linewidth=2, markersize=8, color="red")
    ax.plot(noise_levels, results["degradation"]["RMSE"], "s-", label="RMSE Degradation",
            linewidth=2, markersize=8, color="blue")
    ax.plot(noise_levels, results["degradation"]["MAPE (%)"], "^-", label="MAPE Degradation",
            linewidth=2, markersize=8, color="green")
    ax.axhline(y=0, color="black", linestyle="--", alpha=0.5, linewidth=2)
    ax.axhline(y=-20, color="red", linestyle=":", alpha=0.5, label="-20% threshold (critical)")
    ax.axhline(y=-10, color="orange", linestyle=":", alpha=0.5, label="-10% threshold (warning)")

    ax.set_xlabel("Noise Level (fraction of std)", fontsize=12)
    ax.set_ylabel("Relative Degradation (%)", fontsize=12)
    ax.set_title(f'Metric Degradation vs Noise Level - Model Version {results["model_version"]}',
                 fontsize=14, fontweight="bold")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=10)

    for i, noise in enumerate(noise_levels):
        if results["degradation"]["R2"][i] < -20:
            ax.annotate(f"Critical at noise={noise:.2f}",
                        xy=(noise, results["degradation"]["R2"][i]),
                        xytext=(10, 10), textcoords="offset points",
                        bbox=dict(boxstyle="round,pad=0.5", facecolor="yellow", alpha=0.7),
                        arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=0"))

    plt.tight_layout()

    buf2 = io.BytesIO()
    plt.savefig(buf2, format="png", dpi=300, bbox_inches="tight")
    buf2.seek(0)
    plt.close()

    print(f"Degradation plot logged to MLFlow")

    df_results = pd.DataFrame({
        "noise_level": noise_levels,
        "R2": results["metrics"]["R2"],
        "RMSE": results["metrics"]["RMSE"],
        "MAPE (%)": results["metrics"]["MAPE (%)"],
        "R2_degradation (%)": results["degradation"]["R2"],
        "RMSE_degradation (%)": results["degradation"]["RMSE"],
        "MAPE_degradation (%)": results["degradation"]["MAPE (%)"],
    })

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        df_results.to_csv(f.name, index=False)
        temp_csv_path = f.name

    print(f"Results CSV logged to MLFlow")


if __name__ == "__main__":
    print("Starting Model Performance Test...")
    print("=" * 60)

    results = run_performance_test(
        test_years=[2020],
        test_months=[1, 2, 3],
        test_days=None,
        noise_levels=[0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5],
    )

    print("\n" + "=" * 60)
    print("Performance test completed successfully!")
    print("=" * 60)
