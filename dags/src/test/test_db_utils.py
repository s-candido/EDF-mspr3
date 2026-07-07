"""
Tests for dags/src/batch_prediction/db_utils.py.

Covers: infer_sql_type
Used by the batch_prediction_dag and training_dag (via data_prep).
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import numpy as np
import pytest

from src.batch_prediction.db_utils import infer_sql_type


class TestInferSqlType:
    def test_infer_boolean(self):
        s = pd.Series([True, False, True])
        assert infer_sql_type(s) == "BOOLEAN"

    def test_infer_integer(self):
        s = pd.Series([1, 2, 3])
        assert infer_sql_type(s) == "INTEGER"

    def test_infer_integer_with_na(self):
        s = pd.Series([1, 2, None])
        # pandas may infer float64 for ints with NA; accept both INTEGER and DOUBLE PRECISION
        result = infer_sql_type(s)
        assert result in ("INTEGER", "DOUBLE PRECISION")

    def test_infer_float(self):
        s = pd.Series([1.0, 2.5, 3.7])
        assert infer_sql_type(s) == "DOUBLE PRECISION"

    def test_infer_float_with_integers(self):
        s = pd.Series([1.0, 2.0, 3.0])
        assert infer_sql_type(s) == "DOUBLE PRECISION"

    def test_infer_datetime(self):
        s = pd.Series(pd.to_datetime(["2020-01-01", "2020-02-01"]))
        assert infer_sql_type(s) == "TIMESTAMP"

    def test_infer_text(self):
        s = pd.Series(["hello", "world", "foo"])
        assert infer_sql_type(s) == "TEXT"

    def test_infer_mixed_type_defaults_to_text(self):
        s = pd.Series(["hello", 1, 3.5])
        assert infer_sql_type(s) == "TEXT"

    def test_infer_empty_series(self):
        s = pd.Series(dtype=object)
        assert infer_sql_type(s) == "TEXT"

    def test_infer_nullable_integer(self):
        s = pd.Series([1, 2, None], dtype="Int64")
        assert infer_sql_type(s) == "INTEGER"
