FROM python:3.9-slim

# Set environment variables
ENV MLFLOW_HOME=/mlflow
ENV PATH=$MLFLOW_HOME/bin:$PATH

# Install dependencies
RUN pip install --no-cache-dir mlflow psycopg2-binary

# Create directories for persistent volumes
RUN mkdir -p /mlflow/artifacts /mlflow/data

# Expose MLflow default port
EXPOSE 5000

# Set the working directory
WORKDIR /mlflow

# Command to run MLflow server
CMD ["mlflow", "server", "--backend-store-uri", "sqlite:///mlflow.db", "--default-artifact-root", "/mlflow/artifacts", "--host", "0.0.0.0"]