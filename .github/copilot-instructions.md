# Copilot Instructions

## Repository summary
- Energy consumption ML project with Airflow DAGs, MLflow model registry, and PostgreSQL storage.
- Languages: Python.
- Orchestration: Airflow in Docker.
- Model tracking: MLflow in Docker.
- Data store: PostgreSQL in Docker.
- Key runtime: Docker Compose.

## Build, run, test
- Docker Compose is the primary runtime.
- The following commands are documented but were not validated in this session because command execution was skipped:
  - Build: `docker-compose build`
  - Run: `docker-compose up -d`
- Airflow UI: http://localhost:8080
- MLflow UI: http://localhost:5000
- PostgreSQL port: 5441

## Project layout
- Root files: README.md, docker-compose.yml, requirement.txt, dags.md, dags_fr.md.
- Airflow DAGs: dags/*.py.
- DAG python sources: dags/src/.
- Features pipeline: dags/src/features/features.py.
- Batch prediction: dags/src/batch_prediction/.
- MLflow helpers: dags/src/mlflow/.
- Dockerfiles: docker/.
- Infra scripts: infra/start_airflow.sh, infra/start_mlflow.sh, infra/start_jupyter_nb.sh.
- Notebooks: notebook/.

## Validation and CI
- No CI configuration detected in repo root. Use Docker Compose for validation.

## Key references
- Batch prediction DAG: dags/batch_prediction_dag.py.
- Batch prediction API: dags/src/batch_prediction/batch_prediction.py.
- Data preparation API: dags/src/batch_prediction/data_prep.py.

## Notes for changes
- Do not edit MLflow artifacts under mlflow/.
- Use feature columns consistent with notebook/features_notebook.ipynb.
- Trust these instructions. Only search further if information is missing or incorrect.
