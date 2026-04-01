# K3D - EDF Deployement

To simulate this stack locally while keeping it close to a production environment (using `kubectl`, `k3s`, and Helm), the best approach is to use **k3d**.

**Why k3d?**
*   It runs **k3s** (lightweight Kubernetes) inside **Docker containers**.
*   It allows you to create and destroy clusters instantly (perfect for testing).
*   It uses standard `kubectl`.
*   It isolates the test environment from your host OS.

Here is a step-by-step guide to deploying Airflow, MLflow, and MinIO (for S3 storage simulation) on a local k3s cluster.

---

### 1. Prerequisites

Ensure you have the following installed:
*   **Docker Desktop** (or Docker Engine)
*   **k3d**: `curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash`
*   **kubectl**: `curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"`
*   **Helm**: `curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash`

---

### 2. Create the Local K3s Cluster

Create a cluster with enough memory. Airflow + MLflow + K3s is resource-intensive.

```bash
# Create a cluster named 'ml-platform' with 8GB RAM limit
k3d cluster create ml-platform --memory 8gb --k3s-arg "--disable=traefik@server:0"
```
*Note: We disable Traefik (default in k3s) to avoid conflicts with our own Ingress or port-forwarding setup.*

Verify connection:
```bash
kubectl cluster-info
kubectl get nodes
```

---

### 3. Deploy Storage (MinIO)

MLflow needs an artifact store (like S3). Locally, we use MinIO. Airflow also needs a database, but the Airflow Helm chart handles that internally. We just need MinIO for MLflow artifacts.

```bash
# Add MinIO Helm repo
helm repo add minio https://charts.min.io/
helm repo update

# Install MinIO in a dedicated namespace
kubectl create namespace minio
helm install minio minio/minio --namespace minio --set mode=standalone
```

**Get MinIO Credentials & Endpoint:**
```bash
# Get root user and password
export MINIO_ROOT_USER=$(kubectl get secret minio -n minio -o jsonpath="{.data.rootUser}" | base64 -d)
export MINIO_ROOT_PASSWORD=$(kubectl get secret minio -n minio -o jsonpath="{.data.rootPassword}" | base64 -d)

# Internal DNS name for MLflow to use
export MINIO_ENDPOINT="http://minio.minio.svc.cluster.local:9000"
```

---

### 4. Deploy MLflow

We will use the community MLflow Helm chart. We need to configure it to use the MinIO service we just created.

```bash
# Add MLflow Helm repo
helm repo add community-charts https://community-charts.github.io/helm-charts
helm repo update

kubectl create namespace mlflow

# Install MLflow
helm install mlflow community-charts/mlflow --namespace mlflow \
  --set mlflowTrackingServer.enabled=true \
  --set postgresql.enabled=true \
  --set minio.enabled=false \
  --set mlflowTrackingServer.artifactRoot="s3://mlflow-artifacts/" \
  --set mlflowTrackingServer.extraEnvVars="[
    {\"name\":\"AWS_ACCESS_KEY_ID\",\"value\":\"$MINIO_ROOT_USER\"},
    {\"name\":\"AWS_SECRET_ACCESS_KEY\",\"value\":\"$MINIO_ROOT_PASSWORD\"},
    {\"name\":\"MLFLOW_S3_ENDPOINT_URL\",\"value\":\"$MINIO_ENDPOINT\"},
    {\"name\":\"AWS_DEFAULT_REGION\",\"value\":\"us-east-1\"}
  ]"
```

---

### 5. Deploy Airflow

This is the critical part. The Airflow workers need the `mlflow` python library installed to talk to the MLflow server. We will inject this via the Helm chart values.

```bash
# Add Airflow Helm repo
helm repo add apache-airflow https://airflow.apache.org
helm repo update

kubectl create namespace airflow

# Install Airflow
# We configure the webserver/workers to have mlflow and boto3 (for s3) installed
helm install airflow apache-airflow/airflow --namespace airflow \
  --set executor="LocalExecutor" \
  --set webserver.service.type="ClusterIP" \
  --set postgresql.enabled=true \
  --set redis.enabled=true \
  --set "airflowConfigAnnotations.MLFLOW_TRACKING_URI=http://mlflow.mlflow.svc.cluster.local:5000" \
  --set "workers.extraPipPackages[0]=mlflow" \
  --set "workers.extraPipPackages[1]=boto3" \
  --set "webserver.extraPipPackages[0]=mlflow" \
  --set "webserver.extraPipPackages[1]=boto3" \
  --set "scheduler.extraPipPackages[0]=mlflow" \
  --set "scheduler.extraPipPackages[1]=boto3"
```
*Note: We use `LocalExecutor` for simplicity in local testing. For production simulation, you might prefer `KubernetesExecutor`, but it requires more complex image building.*

---

### 6. Create a Test DAG (Python)

Create a file named `test_mlflow_dag.py` on your local machine. This DAG will train a dummy model and log it to MLflow.

```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import mlflow
import mlflow.sklearn
from sklearn.linear_model import LinearRegression
import os

# Get URI from Airflow Config or Environment
MLFLOW_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow.mlflow.svc.cluster.local:5000")

def train_model():
    # Set the tracking URI to the K8s internal DNS of MLflow
    mlflow.set_tracking_uri(MLFLOW_URI)
    mlflow.set_experiment("airflow-local-test")

    with mlflow.start_run():
        # Dummy data
        X = [[1], [2], [3]]
        y = [2, 4, 6]
        
        model = LinearRegression()
        model.fit(X, y)
        
        # Log parameters and metrics
        mlflow.log_param("model_type", "LinearRegression")
        mlflow.log_metric("score", model.score(X, y))
        
        # Log model
        mlflow.sklearn.log_model(model, "model")
        print(f"Model logged to MLflow at {MLFLOW_URI}")

with DAG(
    'test_mlflow_integration',
    start_date=datetime(2023, 1, 1),
    schedule_interval=None,
    catchup=False
) as dag:

    train_task = PythonOperator(
        task_id='train_and_log',
        python_callable=train_model
    )
```

**How to load this DAG:**
1.  Find the Airflow Webserver pod: `kubectl get pods -n airflow`
2.  Copy the file into the DAGs folder (usually mounted via GitSync or a PVC in Helm, but for quick testing, we can exec into the webserver):
    ```bash
    # Get webserver pod name
    WEBPOD=$(kubectl get pods -n airflow -l component=webserver -o jsonpath="{.items[0].metadata.name}")
    
    # Copy file into the pod
    kubectl cp test_mlflow_dag.py -n airflow $WEBPOD:/opt/airflow/dags/test_mlflow_dag.py
    ```

---

### 7. Access the UIs (Port Forwarding)

Since we are local, we don't need Ingress. We use `kubectl port-forward`. Open three separate terminals.

**Terminal 1: Airflow UI**
```bash
kubectl port-forward svc/airflow-webserver 8080:8080 -n airflow
# Access: http://localhost:8080
# User: admin
# Pass: Get via: kubectl get secret airflow -n airflow -o jsonpath="{.data.admin-password}" | base64 -d
```

**Terminal 2: MLflow UI**
```bash
kubectl port-forward svc/mlflow 5000:5000 -n mlflow
# Access: http://localhost:5000
```

**Terminal 3: MinIO UI**
```bash
kubectl port-forward svc/minio 9001:9001 -n minio
# Access: http://localhost:9001
# User/Pass: See Step 3 variables
```

---

### 8. Verify the Integration

1.  Go to **Airflow UI** (`localhost:8080`).
2.  Enable the `test_mlflow_integration` DAG.
3.  Trigger it manually.
4.  Check the Task Logs. You should see `Model logged to MLflow...`.
5.  Go to **MLflow UI** (`localhost:5000`).
6.  You should see the experiment `airflow-local-test` with the run and the logged model.
7.  Go to **MinIO UI** (`localhost:9001`). You should see the actual model artifacts stored in the bucket.

---

### 9. Cleanup

When you are done testing, wipe the entire environment cleanly.

```bash
k3d cluster delete ml-platform
```
This removes the cluster, all pods, PVCs, and networks created by k3d.

### Common Pitfalls & Tips

1.  **Memory Issues:** If pods stay in `Pending` or `OOMKilled`, your Docker Desktop doesn't have enough RAM allocated. Increase it to at least 8GB (preferably 12GB+).
2.  **Network DNS:** Inside the cluster, Airflow talks to MLflow via `http://mlflow.mlflow.svc.cluster.local:5000`. Do not use `localhost` inside the DAG code, as `localhost` refers to the Pod itself, not your computer.
3.  **Persistent Data:** k3d volumes are ephemeral. If you delete the cluster, data is gone. For longer-term local dev, you can map k3d volumes to host directories.
4.  **Python Versions:** Ensure the Python version in your Airflow Helm chart matches the version you use for your ML code locally to avoid serialization issues with pickle/cloudpickle.

This setup gives you a high-fidelity simulation of a production K8s ML platform without costing cloud money or polluting your host machine.