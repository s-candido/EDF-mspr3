import mlflow
from mlflow.tracking import MlflowClient
import mlflow.sklearn
import joblib
import os
import joblib

import mlflow
import mlflow.sklearn
import joblib
import os

MLFLOW_URL="http://localhost:5000"

# Name of the model to save in MLflow Model Registry
MODEL_NAME="MODEL_EDF"

# Path of the local model file to import 
IMPORT_MODEL_PATH="model.joblib"

mlflow.set_tracking_uri(MLFLOW_URL)

model_path = joblib.load(IMPORT_MODEL_PATH)

model_name = MODEL_NAME

#mlflow.create_experiment("EDF_Model_Experiment")
mlflow.set_experiment("EDF_Model_Experiment")

with mlflow.start_run():
    # Log the artifact
    mlflow.log_artifact("model.joblib", artifact_path=model_name)
    
    # Log the sklearn model
    mlflow.sklearn.log_model(model_path, artifact_path=model_name)
    
    # Register the model (this will create a new version if the model already exists)
    mlflow.register_model(
        f"runs:/{mlflow.active_run().info.run_id}/{model_name}",
        model_name,
    )
    
    print(f"Model registered as '{model_name}' - Run ID: {mlflow.active_run().info.run_id}")

print("Upload complete!")