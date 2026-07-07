"""
Shared fixtures for DAG source tests.
"""

import sys
import os

# Ensure dags/src is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import numpy as np
import pytest


@pytest.fixture
def sample_eco2mix_df() -> pd.DataFrame:
    """Simulates raw eco2mix-style data with typical columns."""
    return pd.DataFrame(
        {
            "perimetre": ["France", "France"],
            "nature": ["Consommation", "Consommation"],
            "date": ["2020-01-01", "2020-01-01"],
            "heures": ["01:00", "02:00"],
            "consommation": [50000, 48000],
            "prevision_j_1": [51000, 49000],
            "prevision_j": [50500, 48500],
            "fioul": [3000, 2900],
            "charbon": [2000, 1900],
            "gaz": [10000, 9800],
            "nucleaire": [30000, 29500],
            "eolien": [5000, 4800],
            "solaire": [0, 0],
            "hydraulique": [4000, 3900],
            "pompage": [500, 480],
            "bioenergies": [1500, 1400],
            "ech_physiques": [500, 400],
            "taux_de_co2": [50, 48],
            "source_file": ["eco2mix_2020.csv", "eco2mix_2020.csv"],
        }
    )


@pytest.fixture
def sample_weather_df() -> pd.DataFrame:
    """Simulates weather data for region features."""
    return pd.DataFrame(
        {
            "city": ["Paris", "Lyon"],
            "temperature_2m": [15.0, 16.0],
            "relative_humidity_2m": [70.0, 65.0],
            "snowfall": [0.0, 0.0],
            "precipitation": [0.5, 0.3],
            "weather_code": [1, 2],
        }
    )


@pytest.fixture
def sample_feature_df() -> pd.DataFrame:
    """Simulates a prepared feature DataFrame for training/prediction."""
    np.random.seed(42)
    n = 20
    return pd.DataFrame(
        {
            "temp_fr": np.random.uniform(-5, 35, n),
            "snow_fr": np.random.uniform(0, 10, n),
            "hour": np.random.randint(0, 24, n),
            "month": np.random.randint(1, 13, n),
            "dayofweek": np.random.randint(0, 7, n),
            "weekend": np.random.randint(0, 2, n),
            "consommation": np.random.uniform(30000, 70000, n),
        }
    )


@pytest.fixture
def sample_X_y(sample_feature_df):
    """Split feature df into X and y for model tests."""
    from sklearn.model_selection import train_test_split

    X = sample_feature_df.drop(columns=["consommation"])
    y = sample_feature_df["consommation"]
    return train_test_split(X, y, test_size=0.3, random_state=42)
