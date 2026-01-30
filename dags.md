# DAGs Documentation - EDF MSPR3 Energy Consumption Management

This document provides a comprehensive overview of all DAGs in the `dags/` directory, including their transformations, tasks, and data flow.

## Table of Contents

1. [DAG Overview](#dag-overview)
2. [Detailed DAG Transformations](#detailed-dag-transformations)
   - [data_ingestion_dag](#data_ingestion_dag)
   - [ml_pipeline_dag](#ml_pipeline_dag)
   - [performance_test_dag](#performance_test_dag)
   - [test_dag](#test_dag)
3. [Supporting Scripts](#supporting-scripts)
4. [Data Flow Architecture](#data-flow-architecture)

## DAG Overview

| DAG Name | Purpose | Schedule | Main Transformations |
|----------|---------|----------|----------------------|
| `data_ingestion_dag` | Load weather and consumption data into PostgreSQL | Manual | Data download → Database ingestion → Feature cleaning → Data aggregation |
| `ml_pipeline_dag` | Complete ML pipeline training and evaluation | Manual | Data loading → Feature engineering → Model training → MLflow registration |
| `performance_test_dag` | Model robustness testing with noise injection | Manual | Model loading → Performance testing → Results logging |
| `test_dag` | Simple test DAG for validation | Manual | Dummy tasks for testing |

---

## Detailed DAG Transformations

### data_ingestion_dag

**File**: `dags/data_ingestion_dag.py`

**Purpose**: Orchestrate the complete data ingestion pipeline from external sources to PostgreSQL database.

**Schedule**: Manual trigger only (`schedule_interval=None`)

**Task Flow**:
```
start → ingestion_job → cleanning_job → aggregation_job → complete
```

#### Transformations:

#### 1. ingestion_job
- **Function**: `run_full_pipeline` from `src.data_ingestion`
- **Transformations**:
  - **Data Download**: Downloads and extracts energy consumption data from 2012 onwards using `download_and_extract(start_year=2012)`
  - **PostgreSQL Ingestion**: Loads consumption data into PostgreSQL using `ingest_postgres()`
  - **Weather Data Ingestion**: Fetches weather data from 2012-2023 using `ingest_weather(2012, 2023)`
  - **Feature Creation**: Creates initial features using `create_features(df)` on loaded data
  - **Data Cleanup**: Removes downloaded files after successful ingestion (`cleanup=True`)

#### 2. cleanning_job
- **Function**: `ingest_features` from `src.db.ingestion_clean_data`
- **Transformations**:
  - **Data Cleaning**: Processes and cleans raw consumption features
  - **Feature Engineering**: Applies cleaning transformations to prepare data for analysis
  - **Database Storage**: Stores cleaned features in PostgreSQL database

#### 3. aggregation_job
- **Function**: `ingest_conso_meteo` from `src.db.ingestion_conso_meteo_sql`
- **Transformations**:
  - **Data Aggregation**: Combines consumption and weather data
  - **Time-based Aggregation**: Creates aggregated features with temporal dimensions
  - **Final Feature Storage**: Stores aggregated data in partitioned table structure

---

### ml_pipeline_dag

**File**: `dags/ml_pipeline_dag.py`

**Purpose**: Complete machine learning pipeline from data loading to model registration in MLflow.

**Schedule**: Manual trigger only (`schedule_interval=None`)

**Task Flow**:
```
start → preprocessing_task → complete
```

#### Transformations:

#### preprocessing_task
- **Function**: `run_ml_pipeline` from `src.main`
- **Transformations**:
  - **Data Loading**: Loads all data from local directory using `load_all_data(data_dir)`
  - **Feature Engineering**: Applies comprehensive feature creation using `create_features(df)`
    - Temporal features (hour, day, month, year)
    - Weather-related features
    - Consumption patterns
  - **Data Preprocessing**:
    - Target variable conversion to numeric: `pd.to_numeric(df[target], errors="coerce")`
    - Missing value handling: `X.fillna(0)`, `y.fillna(0)`
    - Train-test split: `train_test_split(X, y, test_size=0.2, random_state=42)`
  - **Model Training**: Trains multiple models using `train_models(X_train, y_train)`
  - **Model Evaluation**: Evaluates all models using `evaluate_model(model, X_test, y_test)`
    - Metrics: R², RMSE, MAPE
    - Best model selection based on R² score
  - **MLflow Integration**:
    - Experiment tracking: `mlflow.set_experiment("EDF_Model_Experiment")`
    - Parameter logging: source files, model type
    - Metric logging: R² score
    - Model registration: `mlflow.register_model(model_uri, "MODEL_EDF")`
  - **Weather Data Fetching**: Fetches weather data using `fetch_weather("2020-01-01", "2020-12-31")`

---

### performance_test_dag

**File**: `dags/performance_test_dag.py`

**Purpose**: Robustness testing of the latest ML model with progressive noise injection.

**Schedule**: Manual trigger only (`schedule_interval=None`)

**Task Flow**:
```
start → run_performance_test → complete
```

#### Transformations:

#### run_performance_test
- **Function**: `run_performance_test_task` (wrapper) calling `run_performance_test` from `src.test.performance_test`
- **Transformations**:
  - **Model Loading**:
    - Fetches latest model version from MLflow registry: `get_latest_model_version("MODEL_EDF")`
    - Loads model: `load_model(model_uri)` where `model_uri = f"models:/{MODEL_NAME}/{model_version}"`
  - **Test Data Preparation**:
    - Loads data using `load_all_data(DATA_DIR)`
    - Applies feature engineering: `create_features(df)`
    - Uses first 1000 samples for testing: `X_test = X.head(1000)`
  - **Noise Injection Testing**:
    - Tests 14 noise levels: `[0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]`
    - For each noise level:
      - Adds Gaussian noise: `noise = np.random.normal(0, noise_level * col_std, size=X_noisy[col].shape)`
      - Evaluates model performance: `evaluate_model(model, X_noisy, y_test)`
  - **Metrics Calculation**:
    - **Primary Metrics**: R², RMSE, MAPE at each noise level
    - **Degradation Metrics**: Percentage change relative to baseline (noise=0.0)
    - Formula: `((metric_noisy - metric_baseline) / abs(metric_baseline)) * 100`
  - **Results Logging to MLflow**:
    - Experiment: "Performance_Test"
    - Parameters: model_version, noise_levels
    - Metrics: All performance metrics and degradation values at each noise level
    - Artifacts:
      - Performance plots (4-panel summary)
      - Degradation analysis plots with threshold markers
      - CSV results: `performance_results.csv`
  - **Threshold Analysis**:
    - **Warning threshold**: -10% degradation
    - **Critical threshold**: -20% degradation
    - Automatic annotation of critical points on plots

---

### test_dag

**File**: `dags/test_dag.py`

**Purpose**: Simple test DAG for Airflow validation and debugging.

**Schedule**: Manual trigger only

**Task Flow**:
```
dummy_task_run_1 → dummy_task_run_2
```

#### Transformations:
- **Basic Validation**: Uses `DummyOperator` tasks to verify Airflow functionality
- **No Data Processing**: Purely for infrastructure testing

---

## Supporting Scripts

### Core Data Processing Scripts

#### src/data_ingestion.py
- **run_full_pipeline()**: Main orchestration function
  - Downloads consumption data (2012+)
  - Ingests to PostgreSQL
  - Fetches weather data (2012-2023)
  - Creates initial features
  - Cleans up temporary files

#### src/main.py
- **run_ml_pipeline()**: Complete ML pipeline
  - Data loading and feature engineering
  - Multi-model training and evaluation
  - MLflow model registration
  - Weather data integration

### Database Ingestion Scripts

#### src/db/ingestion_postgre.py
- Loads consumption data into PostgreSQL tables

#### src/db/ingestion_weather.py
- Fetches and stores weather data from external APIs

#### src/db/ingestion_clean_data.py
- **ingest_features()**: Data cleaning and feature preprocessing

#### src/db/ingestion_conso_meteo_sql.py
- **ingest_conso_meteo()**: Aggregates consumption and weather data

### Data Loading Scripts

#### src/data/data_loader.py
- **load_all_data()**: Loads consumption data from local files
- **load_from_postgres()**: Retrieves data from PostgreSQL

#### src/data/weather_loader.py
- **fetch_weather()**: Retrieves weather data for specified date ranges

### Feature Engineering Scripts

#### src/features/features.py
- **create_features()**: Creates temporal and consumption-based features

#### src/features/weather_features.py
- Weather-specific feature engineering functions

### Modeling Scripts

#### src/modeling/train.py
- **train_models()**: Trains multiple ML models (likely regression models)

#### src/modeling/evaluate.py
- **evaluate_model()**: Calculates R², RMSE, MAPE metrics

### MLflow Integration Scripts

#### src/mlflow/pull_model_from_mlflow.py
- Retrieves latest model versions from MLflow registry

#### src/mlflow/push_model_to_mlflow.py
- Registers trained models in MLflow

### Testing Scripts

#### src/test/performance_test.py
- **run_performance_test()**: Comprehensive noise injection testing
- **add_noise_to_features()**: Adds controlled Gaussian noise to features
- **get_latest_model_version()**: Fetches latest model from registry

---

## Data Flow Architecture

### Data Sources
1. **Energy Consumption Data**: External data files (XLS/CSV format)
2. **Weather Data**: API-based weather data fetch
3. **Historical Data**: PostgreSQL database storage

### Transformation Pipeline

#### 1. Data Ingestion Phase
```
External Files → Download → PostgreSQL → Weather API → Feature Creation → Clean Features
```

#### 2. ML Training Phase
```
Database → Load Data → Feature Engineering → Train Models → Evaluate → Register Best Model
```

#### 3. Testing Phase
```
MLflow Registry → Load Model → Noise Injection → Performance Evaluation → Results Logging
```

### Database Tables
- **Raw Data**: `weather_data`, consumption tables
- **Processed Data**: `features_data`
- **Aggregated Data**: Partitioned tables by year/month

### MLflow Integration
- **Experiment**: "EDF_Model_Experiment" for training
- **Experiment**: "Performance_Test" for robustness testing
- **Model Registry**: "MODEL_EDF" for model versioning

### Key Features Created
- **Temporal Features**: Hour, day, month, year, day of week
- **Weather Features**: Temperature, humidity, precipitation, wind
- **Consumption Features**: Historical consumption patterns, lag features
- **Aggregated Features**: Time-based aggregations, rolling statistics

---

## Configuration

### Environment Variables
- `MLFLOW_URL`: "http://mlflow:5000"
- `DATA_DIR`: "/opt/airflow/dags/src/data_folder"
- `MODEL_NAME`: "MODEL_EDF"

### Database Configuration
- **Host**: "edf_postgresql"
- **Database**: "postgres"
- **User/Password**: "postgres"
- **Port**: 5432

### Data Parameters
- **Training Period**: 2012-2023 (weather), variable (consumption)
- **Test Size**: 20% of data
- **Target Variable**: "consommation"
- **Random State**: 42 (for reproducibility)

This documentation provides a complete overview of all transformations and data flows within the DAGs, enabling understanding of the entire EDF energy consumption management pipeline.