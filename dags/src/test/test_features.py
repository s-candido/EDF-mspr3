"""
Tests for dags/src/features/features.py.

Covers: aggregate_hourly, create_features, aggregate_hourly_region, create_region_features
These pure-pandas functions are used by the data_ingestion_dag and ml_pipeline_dag.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import numpy as np
import pytest

from src.features.features import (
    aggregate_hourly,
    create_features,
    aggregate_hourly_region,
    create_region_features,
)


class TestAggregateHourly:
    def test_aggregate_hourly_returns_dataframe(self, sample_eco2mix_df):
        result = aggregate_hourly(sample_eco2mix_df)
        assert isinstance(result, pd.DataFrame)

    def test_aggregate_hourly_aggregates_by_hour(self):
        # Two rows with the SAME hour → collapse to 1
        df = pd.DataFrame(
            {
                "date": ["2020-01-01", "2020-01-01"],
                "heures": ["01:00", "01:00"],
                "consommation": [100, 200],
                "source_file": ["test.csv", "test.csv"],
                "perimetre": ["France", "France"],
                "nature": ["Consommation", "Consommation"],
            }
        )
        result = aggregate_hourly(df)
        assert len(result) == 1

    def test_aggregate_hourly_has_datetime_column(self, sample_eco2mix_df):
        result = aggregate_hourly(sample_eco2mix_df)
        assert "datetime" in result.columns
        assert pd.api.types.is_datetime64_any_dtype(result["datetime"])

    def test_aggregate_hourly_numeric_columns_are_averaged(self):
        df = pd.DataFrame(
            {
                "date": ["2020-01-01", "2020-01-01"],
                "heures": ["01:00", "01:00"],
                "consommation": [100, 200],
                "source_file": ["test.csv", "test.csv"],
                "perimetre": ["France", "France"],
                "nature": ["Consommation", "Consommation"],
            }
        )
        result = aggregate_hourly(df)
        assert result["consommation"].iloc[0] == 150.0

    def test_aggregate_hourly_replaces_nd_with_na(self):
        df = pd.DataFrame(
            {
                "date": ["2020-01-01"],
                "heures": ["01:00"],
                "consommation": [100],
                "source_file": ["test.csv"],
                "perimetre": ["France"],
                "nature": ["Consommation"],
            }
        )
        df.loc[0, "consommation"] = "ND"
        result = aggregate_hourly(df)
        assert pd.isna(result["consommation"].iloc[0]) or result["consommation"].iloc[0] == 0

    def test_aggregate_hourly_multiple_hours(self):
        df = pd.DataFrame(
            {
                "date": ["2020-01-01", "2020-01-01"],
                "heures": ["01:00", "02:00"],
                "consommation": [100, 200],
                "source_file": ["test.csv", "test.csv"],
                "perimetre": ["France", "France"],
                "nature": ["Consommation", "Consommation"],
            }
        )
        result = aggregate_hourly(df)
        # Two different hours → 2 rows
        assert len(result) == 2

    def test_aggregate_hourly_empty_dataframe(self):
        df = pd.DataFrame(
            {"date": pd.Series(dtype=str), "heures": pd.Series(dtype=str)}
        )
        result = aggregate_hourly(df)
        assert isinstance(result, pd.DataFrame)


class TestCreateFeatures:
    def test_create_features_returns_dataframe(self, sample_eco2mix_df):
        result = create_features(sample_eco2mix_df)
        assert isinstance(result, pd.DataFrame)

    def test_create_features_adds_time_columns(self, sample_eco2mix_df):
        result = create_features(sample_eco2mix_df)
        for col in ["year", "hour", "day", "month", "dayofweek", "weekend"]:
            assert col in result.columns, f"Missing column: {col}"

    def test_create_features_removes_raw_columns(self, sample_eco2mix_df):
        result = create_features(sample_eco2mix_df)
        for col in ["perimetre", "nature", "source_file", "date", "heures"]:
            assert col not in result.columns, f"Raw column still present: {col}"

    def test_create_features_weekend_detection(self):
        # 2020-01-06 is a Monday → weekend=0
        df = pd.DataFrame(
            {
                "date": ["2020-01-06"],
                "heures": ["01:00"],
                "consommation": [50000],
                "source_file": ["test.csv"],
                "perimetre": ["France"],
                "nature": ["Consommation"],
            }
        )
        result = create_features(df)
        assert result["weekend"].iloc[0] == 0

    def test_create_features_fills_na(self):
        df = pd.DataFrame(
            {
                "date": ["2020-01-01"],
                "heures": ["01:00"],
                "consommation": [pd.NA],
                "source_file": ["test.csv"],
                "perimetre": ["France"],
                "nature": ["Consommation"],
            }
        )
        result = create_features(df)
        # After fillna(0), consommation should be 0
        assert result["consommation"].iloc[0] == 0

    def test_create_features_no_mutation_of_input(self, sample_eco2mix_df):
        original_cols = set(sample_eco2mix_df.columns)
        _ = create_features(sample_eco2mix_df)
        assert set(sample_eco2mix_df.columns) == original_cols


class TestAggregateHourlyRegion:
    def test_aggregate_hourly_region_has_region_column(self):
        df = pd.DataFrame(
            {
                "region": ["Île-de-France", "Île-de-France"],
                "date": ["2020-01-01", "2020-01-01"],
                "heures": ["01:00", "01:00"],
                "consommation": [50000, 48000],
                "source_file": ["test.csv", "test.csv"],
                "perimetre": ["France", "France"],
                "nature": ["Consommation", "Consommation"],
            }
        )
        result = aggregate_hourly_region(df)
        assert "region" in result.columns

    def test_aggregate_hourly_region_groups_by_region_and_hour(self):
        df = pd.DataFrame(
            {
                "region": ["IDF", "IDF", "BRE"],
                "date": ["2020-01-01", "2020-01-01", "2020-01-01"],
                "heures": ["01:00", "01:00", "01:00"],
                "consommation": [100, 200, 300],
                "source_file": ["t.csv", "t.csv", "t.csv"],
                "perimetre": ["F", "F", "F"],
                "nature": ["C", "C", "C"],
            }
        )
        result = aggregate_hourly_region(df)
        # 2 regions × 1 hour slot = 2 rows
        assert len(result) == 2


class TestCreateRegionFeatures:
    def test_create_region_features_adds_time_columns(self):
        df = pd.DataFrame(
            {
                "region": ["IDF"],
                "date": ["2020-01-06"],
                "heures": ["01:00"],
                "consommation": [50000],
                "source_file": ["test.csv"],
                "perimetre": ["France"],
                "nature": ["Consommation"],
            }
        )
        result = create_region_features(df)
        for col in ["year", "hour", "day", "month", "dayofweek", "weekend"]:
            assert col in result.columns

    def test_create_region_features_removes_raw_columns(self):
        df = pd.DataFrame(
            {
                "region": ["IDF"],
                "date": ["2020-01-06"],
                "heures": ["01:00"],
                "consommation": [50000],
                "source_file": ["test.csv"],
                "perimetre": ["France"],
                "nature": ["Consommation"],
            }
        )
        result = create_region_features(df)
        for col in ["perimetre", "nature", "source_file", "date", "heures"]:
            assert col not in result.columns
