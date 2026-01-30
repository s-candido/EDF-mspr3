# Change Log

## 2026-01-30

- Added shared data preparation job for batch prediction.
- Updated batch prediction DAG with prepare/predict tasks.
- Refactored batch prediction helpers into shared DB utilities.
- Added documentation links and usage examples.
- Added monthly per-year model metrics review and consommation plot in the Cyril notebook.

References:
- [UsageExamples.md](UsageExamples.md)
- [dags/batch_prediction_dag.py](dags/batch_prediction_dag.py)
- [dags/src/batch_prediction/batch_prediction.py](dags/src/batch_prediction/batch_prediction.py)
- [dags/src/batch_prediction/data_prep.py](dags/src/batch_prediction/data_prep.py)
- [local/experiments/cyril_notebook.ipynb](local/experiments/cyril_notebook.ipynb)
