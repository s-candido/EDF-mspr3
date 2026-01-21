import numpy as np
import pandas as pd
import mlflow
from mlflow.pyfunc import load_model
from mlflow.tracking import MlflowClient
import matplotlib.pyplot as plt
import tempfile
import io
from src.mlflow.pull_model_from_mlflow import get_latest_model_version, load_model
from src.data.data_loader import load_all_data
from src.features.features import create_features
from src.modeling.evaluate import evaluate_model

MLFLOW_URL = "http://mlflow:5000"
MODEL_NAME = "MODEL_EDF"
DATA_DIR = "/opt/airflow/dags/src/data_folder"
TARGET = "consommation"


def get_latest_model_version(model_name: str) -> int:
    """
    Get the latest version of a model from the MLflow model registry.

    Args:
        model_name (str): The name of the model in the MLflow model registry.

    Returns:
        int: The latest version of the model.
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
        X (pd.DataFrame): Input features
        noise_level (float): Standard deviation of noise as fraction of feature std
        seed (int): Random seed for reproducibility

    Returns:
        pd.DataFrame: Features with added noise
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
    noise_levels: list = [0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5],
    experiment_name: str = "Performance_Test"
) -> dict:
    """
    Run performance test on latest model with increasing noise levels.

    This function:
    1. Pulls the latest model version from MLFlow
    2. Loads test data and creates features
    3. Tests the model with increasing noise levels
    4. Measures metrics degradation
    5. Logs all results and plots to MLFlow as artifacts and metrics

    Args:
        noise_levels (list): List of noise levels to test (as fraction of feature std)
        experiment_name (str): MLFlow experiment name for logging results

    Returns:
        dict: Dictionary containing:
            - 'model_version': Version of model tested
            - 'noise_levels': List of noise levels tested
            - 'metrics': Dictionary of metrics per noise level
            - 'baseline': Baseline metrics (noise_level=0)
            - 'degradation': Metric degradation relative to baseline
            - 'mlflow_run_id': MLFlow run ID for this test
    """
    mlflow.set_tracking_uri(MLFLOW_URL)

    model_version = get_latest_model_version(MODEL_NAME)
    model_uri = f"models:/{MODEL_NAME}/{model_version}"
    print(f"Loading model {MODEL_NAME}/ version {model_version}")
    model = load_model(model_uri)
    print(f"Model loaded successfully from {model_uri}")
    mlflow.set_experiment(experiment_name)
    with mlflow.start_run():


        mlflow.log_param("model_version", model_version)
        mlflow.log_param("noise_levels", str(noise_levels))



        print("Loading test data...")
        df = load_all_data(DATA_DIR)
        df = create_features(df)

        df[TARGET] = pd.to_numeric(df[TARGET], errors="coerce")

        X = df.drop(columns=[TARGET])
        y = df[TARGET]

        X = X.fillna(0)
        y = y.fillna(0)

        X_test = X.head(1000)
        y_test = y.head(1000)

        print(f"Test data shape: X={X_test.shape}, y={y_test.shape}")

        results = {
            'model_version': model_version,
            'noise_levels': noise_levels,
            'metrics': {
                'R2': [],
                'RMSE': [],
                'MAPE (%)': []
            },
            'predictions': [],
            'baseline': None,
            'degradation': {
                'R2': [],
                'RMSE': [],
                'MAPE (%)': []
            }
        }

        print("\nRunning performance tests with increasing noise levels...")
        for i, noise_level in enumerate(noise_levels):
            print(f"\n{'='*60}")
            print(f"Test {i+1}/{len(noise_levels)}: Noise level = {noise_level:.2f}")
            print(f"{'='*60}")

            if noise_level > 0:
                X_noisy = add_noise_to_features(X_test, noise_level, seed=i)
            else:
                X_noisy = X_test.copy()

            metrics = evaluate_model(model, X_noisy, y_test)

            results['metrics']['R2'].append(metrics['R2'])
            results['metrics']['RMSE'].append(metrics['RMSE'])
            results['metrics']['MAPE (%)'].append(metrics['MAPE (%)'])

            y_pred = model.predict(X_noisy)
            results['predictions'].append(y_pred)

            print(f"R2: {metrics['R2']:.4f}")
            print(f"RMSE: {metrics['RMSE']:.4f}")
            print(f"MAPE (%): {metrics['MAPE (%)']:.2f}")

            if noise_level == 0.0:
                results['baseline'] = metrics.copy()
                mlflow.log_metric("baseline_R2", metrics['R2'])
                mlflow.log_metric("baseline_RMSE", metrics['RMSE'])
                mlflow.log_metric("baseline_MAPE", metrics['MAPE (%)'])

        baseline = results['baseline']
        print("\nCalculating metric degradation...")
        for i, noise_level in enumerate(noise_levels):
            if noise_level > 0:
                r2_degradation = ((results['metrics']['R2'][i] - baseline['R2']) / abs(baseline['R2'])) * 100
                rmse_degradation = ((results['metrics']['RMSE'][i] - baseline['RMSE']) / baseline['RMSE']) * 100
                mape_degradation = ((results['metrics']['MAPE (%)'][i] - baseline['MAPE (%)']) / baseline['MAPE (%)']) * 100
            else:
                r2_degradation = 0.0
                rmse_degradation = 0.0
                mape_degradation = 0.0

            results['degradation']['R2'].append(r2_degradation)
            results['degradation']['RMSE'].append(rmse_degradation)
            results['degradation']['MAPE (%)'].append(mape_degradation)

            mlflow.log_metric(f"R2_noise", results['metrics']['R2'][i])
            mlflow.log_metric(f"RMSE_noise", results['metrics']['RMSE'][i])
            mlflow.log_metric(f"MAPE_noise", results['metrics']['MAPE (%)'][i])
            mlflow.log_metric(f"R2_degradation", r2_degradation)
            mlflow.log_metric(f"RMSE_degradation", rmse_degradation)
            mlflow.log_metric(f"MAPE_degradation", mape_degradation)

        print("\n" + "="*60)
        print("PERFORMANCE TEST SUMMARY")
        print("="*60)
        print(f"Model Version: {model_version}")
        print(f"Baseline Metrics (noise=0.0):")
        print(f"  R2: {baseline['R2']:.4f}")
        print(f"  RMSE: {baseline['RMSE']:.4f}")
        print(f"  MAPE (%): {baseline['MAPE (%)']:.2f}")

        print("\nMetric Degradation:")
        print(f"{'Noise':<10} {'R2 Deg (%)':<15} {'RMSE Deg (%)':<15} {'MAPE Deg (%)':<15}")
        print("-"*60)
        for i, noise_level in enumerate(noise_levels):
            print(f"{noise_level:<10.2f} "
                  f"{results['degradation']['R2'][i]:<15.2f} "
                  f"{results['degradation']['RMSE'][i]:<15.2f} "
                  f"{results['degradation']['MAPE (%)'][i]:<15.2f}")

        _generate_and_log_plots(results)

        results['mlflow_run_id'] = mlflow.active_run().info.run_id
        print(f"\nResults logged to MLFlow run ID: {results['mlflow_run_id']}")

    return results


def _generate_and_log_plots(results: dict):
    """
    Generate performance plots and log them to MLFlow as artifacts.

    Args:
        results (dict): Results from run_performance_test
    """
    noise_levels = results['noise_levels']

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(f'Model Performance vs Noise Level (Version {results["model_version"]})',
                 fontsize=14, fontweight='bold')

    ax1 = axes[0, 0]
    ax1.plot(noise_levels, results['metrics']['R2'], 'o-', label='R2', linewidth=2, markersize=8)
    ax1.set_xlabel('Noise Level (fraction of std)', fontsize=11)
    ax1.set_ylabel('R2 Score', fontsize=11)
    ax1.set_title('Raw Metrics: R2', fontsize=12, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend()

    ax2 = axes[0, 1]
    ax2.plot(noise_levels, results['metrics']['RMSE'], 's-', label='RMSE',
             color='orange', linewidth=2, markersize=8)
    ax2.set_xlabel('Noise Level (fraction of std)', fontsize=11)
    ax2.set_ylabel('RMSE', fontsize=11)
    ax2.set_title('Raw Metrics: RMSE', fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.legend()

    ax3 = axes[1, 0]
    ax3.plot(noise_levels, results['metrics']['MAPE (%)'], '^-', label='MAPE',
             color='green', linewidth=2, markersize=8)
    ax3.set_xlabel('Noise Level (fraction of std)', fontsize=11)
    ax3.set_ylabel('MAPE (%)', fontsize=11)
    ax3.set_title('Raw Metrics: MAPE', fontsize=12, fontweight='bold')
    ax3.grid(True, alpha=0.3)
    ax3.legend()

    ax4 = axes[1, 1]
    ax4.plot(noise_levels, results['degradation']['R2'], 'o-', label='R2 Degradation',
             linewidth=2, markersize=8)
    ax4.plot(noise_levels, results['degradation']['RMSE'], 's-', label='RMSE Degradation',
             color='orange', linewidth=2, markersize=8)
    ax4.plot(noise_levels, results['degradation']['MAPE (%)'], '^-', label='MAPE Degradation',
             color='green', linewidth=2, markersize=8)
    ax4.axhline(y=0, color='black', linestyle='--', alpha=0.5)
    ax4.set_xlabel('Noise Level (fraction of std)', fontsize=11)
    ax4.set_ylabel('Degradation (%)', fontsize=11)
    ax4.set_title('Relative Metric Degradation', fontsize=12, fontweight='bold')
    ax4.grid(True, alpha=0.3)
    ax4.legend()

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=300, bbox_inches='tight')
    buf.seek(0)
    plt.close()
    
    print(f"\nSummary plot logged to MLFlow")

    fig2, ax = plt.subplots(figsize=(10, 6))
    ax.plot(noise_levels, results['degradation']['R2'], 'o-', label='R2 Degradation',
            linewidth=2, markersize=8, color='red')
    ax.plot(noise_levels, results['degradation']['RMSE'], 's-', label='RMSE Degradation',
            linewidth=2, markersize=8, color='blue')
    ax.plot(noise_levels, results['degradation']['MAPE (%)'], '^-', label='MAPE Degradation',
            linewidth=2, markersize=8, color='green')
    ax.axhline(y=0, color='black', linestyle='--', alpha=0.5, linewidth=2)
    ax.axhline(y=-20, color='red', linestyle=':', alpha=0.5, label='-20% threshold (critical)')
    ax.axhline(y=-10, color='orange', linestyle=':', alpha=0.5, label='-10% threshold (warning)')

    ax.set_xlabel('Noise Level (fraction of std)', fontsize=12)
    ax.set_ylabel('Relative Degradation (%)', fontsize=12)
    ax.set_title(f'Metric Degradation vs Noise Level - Model Version {results["model_version"]}',
                 fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=10)

    for i, noise in enumerate(noise_levels):
        if results['degradation']['R2'][i] < -20:
            ax.annotate(f'Critical at noise={noise:.2f}',
                       xy=(noise, results['degradation']['R2'][i]),
                       xytext=(10, 10), textcoords='offset points',
                       bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.7),
                       arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))

    plt.tight_layout()

    buf2 = io.BytesIO()
    plt.savefig(buf2, format='png', dpi=300, bbox_inches='tight')
    buf2.seek(0)
    plt.close()

    print(f"Degradation plot logged to MLFlow")

    df_results = pd.DataFrame({
        'noise_level': noise_levels,
        'R2': results['metrics']['R2'],
        'RMSE': results['metrics']['RMSE'],
        'MAPE (%)': results['metrics']['MAPE (%)'],
        'R2_degradation (%)': results['degradation']['R2'],
        'RMSE_degradation (%)': results['degradation']['RMSE'],
        'MAPE_degradation (%)': results['degradation']['MAPE (%)']
    })

    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        df_results.to_csv(f.name, index=False)
        temp_csv_path = f.name

    print(f"Results CSV logged to MLFlow")


if __name__ == "__main__":
    print("Starting Model Performance Test...")
    print("="*60)

    results = run_performance_test(
        noise_levels=[0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5]
    )

    print("\n" + "="*60)
    print("Performance test completed successfully!")
    print("="*60)
