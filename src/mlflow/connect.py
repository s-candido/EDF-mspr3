import mlflow

# Set the tracking URI to the MLflow server
mlflow.set_tracking_uri("http://localhost:5000")

# Example: Log a simple experiment
with mlflow.start_run():
    mlflow.log_param("param1", 5)
    mlflow.log_metric("metric1", 0.89)
    mlflow.log_artifact("path/to/your/model.joblib", artifact_path="models")

print("Experiment logged successfully!")