# Usage Examples

## Documentation links

- [README.md](README.md)
- [ChangeLog.md](ChangeLog.md)
- [dags.md](dags.md)
- [dags_fr.md](dags_fr.md)
- [local/experiments/cyril_notebook.ipynb](local/experiments/cyril_notebook.ipynb)

### Import / Load the Data

Run the "Data Ingestion DAG" with No Args for import the total data.

### Train and Log Model

Run the "Trainning Data DAG" with Args : selected_years.

### Train and Log Model

Run the "Batch Prediction DAG" with Args :

```json
{
    "selected_years": [2020],
    "selected_months": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    "selected_days": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31] 
}
```





## Batch prediction (Python call)

Example usage of `batch_prediction()` with explicit feature columns.

```python
from src.batch_prediction.batch_prediction import batch_prediction

rows = batch_prediction(
    model_name="MODEL_EDF",
    source_table="batch_prediction_features",
    prediction_table="batch_predictions",
    feature_columns=["temp_fr", "snow_fr", "hour", "month", "dayofweek", "weekend"],
)
print(rows)
```

## Data preparation (Python call)

Example usage of `prepare_batch_prediction_data()` to stage features into a dedicated table.

```python
from src.batch_prediction.data_prep import prepare_batch_prediction_data

rows = prepare_batch_prediction_data(
    source_table="aggregated_conso_weather",
    prepared_table="batch_prediction_features",
    feature_columns=["temp_fr", "snow_fr", "hour", "month", "dayofweek", "weekend"],
)
print(rows)
```

## Notebook model analysis

Monthly metrics and consumption analysis are available in the Cyril notebook:

- [local/experiments/cyril_notebook.ipynb](local/experiments/cyril_notebook.ipynb)
