"""
Tests for dags/src/db/ingestion_postgre.py.

Covers: file_checksum, clean_dataframe
These are used by the data_ingestion_dag via ingest_postgres → run_full_pipeline.
"""

import sys
import os
import tempfile
import hashlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import numpy as np
import pytest
from pathlib import Path

from src.db.ingestion_postgre import file_checksum, clean_dataframe


class TestFileChecksum:
    def test_checksum_is_hex_string(self):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            f.write(b"a,b,c\n1,2,3")
            tmp = f.name
        try:
            result = file_checksum(Path(tmp))
            assert isinstance(result, str)
            assert len(result) == 32  # MD5 hexdigest
            assert all(c in "0123456789abcdef" for c in result)
        finally:
            os.unlink(tmp)

    def test_checksum_deterministic(self):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            f.write(b"hello,world")
            tmp = f.name
        try:
            c1 = file_checksum(Path(tmp))
            c2 = file_checksum(Path(tmp))
            assert c1 == c2
        finally:
            os.unlink(tmp)

    def test_checksum_changes_on_content_change(self):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            f.write(b"version1")
            tmp = f.name
        try:
            c1 = file_checksum(Path(tmp))
            with open(tmp, "w") as f:
                f.write("version2")
            c2 = file_checksum(Path(tmp))
            assert c1 != c2
        finally:
            os.unlink(tmp)

    def test_checksum_matches_hashlib(self):
        content = b"test content for md5"
        expected = hashlib.md5(content).hexdigest()
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            f.write(content)
            tmp = f.name
        try:
            result = file_checksum(Path(tmp))
            assert result == expected
        finally:
            os.unlink(tmp)


class TestCleanDataframe:
    def test_clean_dataframe_returns_dataframe(self):
        df = pd.DataFrame({"consommation": [100, 200]})
        result = clean_dataframe(df)
        assert isinstance(result, pd.DataFrame)

    def test_clean_dataframe_replaces_nd_with_na(self):
        df = pd.DataFrame({"consommation": ["ND", 100, "ND"]})
        result = clean_dataframe(df)
        assert result["consommation"].isna().sum() == 2

    def test_clean_dataframe_replaces_nan_string(self):
        df = pd.DataFrame({"consommation": ["nan", 100]})
        result = clean_dataframe(df)
        assert result["consommation"].isna().sum() == 1

    def test_clean_dataframe_replaces_empty_string(self):
        df = pd.DataFrame({"consommation": ["", 100]})
        result = clean_dataframe(df)
        assert result["consommation"].isna().sum() == 1

    def test_clean_dataframe_renames_columns(self):
        df = pd.DataFrame(
            {
                "hydraulique_fil_de_leeau_eclusee": [100],
                "consommation": [50000],
                "date": ["2020-01-01"],
                "heures": ["01:00"],
                "perimetre": ["France"],
                "nature": ["Consommation"],
            }
        )
        result = clean_dataframe(df)
        assert "hydraulique_fil_de_leau_eclusee" in result.columns

    def test_clean_dataframe_reindexes_to_expected_cols(self):
        df = pd.DataFrame({"consommation": [100]})
        result = clean_dataframe(df)
        # Should have all EXPECTED_COLS after reindex
        expected_cols = [
            "perimetre", "nature", "date", "heures", "consommation",
            "prevision_j_1", "prevision_j", "fioul", "charbon", "gaz",
            "nucleaire", "eolien", "solaire", "hydraulique", "pompage",
            "bioenergies", "ech_physiques", "taux_de_co2",
            "ech_comm_angleterre", "ech_comm_espagne",
            "ech_comm_italie", "ech_comm_suisse",
            "ech_comm_allemagne_belgique",
            "fioul_tac", "fioul_cogen", "fioul_autres",
            "gaz_tac", "gaz_cogen", "gaz_ccg", "gaz_autres",
            "hydraulique_fil_de_leau_eclusee",
            "hydraulique_lacs", "hydraulique_step_turbinage",
            "bioenergies_dechets", "bioenergies_biomasse",
            "bioenergies_biogaz", "stockage_batterie",
            "destockage_batterie", "eolien_terrestre",
            "eolien_offshore", "source_file",
        ]
        for col in expected_cols:
            assert col in result.columns, f"Missing expected column: {col}"

    def test_clean_dataframe_converts_numeric_columns(self):
        df = pd.DataFrame(
            {
                "consommation": ["50000", "60000", "ND"],
                "perimetre": ["France", "France", "France"],
                "date": ["2020-01-01", "2020-01-01", "2020-01-01"],
                "heures": ["01:00", "02:00", "03:00"],
                "nature": ["Consommation", "Consommation", "Consommation"],
            }
        )
        result = clean_dataframe(df)
        # consommation should be numeric (majority numeric)
        assert pd.api.types.is_float_dtype(result["consommation"])

    def test_clean_dataframe_preserves_string_columns(self):
        df = pd.DataFrame(
            {
                "stockage_batterie": ["yes", "no", None],
                "consommation": [100, 200, 300],
                "perimetre": ["F", "F", "F"],
                "date": ["2020-01-01", "2020-01-01", "2020-01-01"],
                "heures": ["01:00", "02:00", "03:00"],
                "nature": ["C", "C", "C"],
            }
        )
        result = clean_dataframe(df)
        # stockage_batterie is mostly text → stays string (object or string dtype)
        assert pd.api.types.is_string_dtype(result["stockage_batterie"]) or pd.api.types.is_object_dtype(result["stockage_batterie"])

    def test_clean_dataframe_does_not_mutate_original(self):
        df = pd.DataFrame({"consommation": [100, "ND"]})
        original = df.copy()
        _ = clean_dataframe(df)
        pd.testing.assert_frame_equal(df, original)

    def test_clean_dataframe_handles_empty(self):
        df = pd.DataFrame()
        result = clean_dataframe(df)
        assert isinstance(result, pd.DataFrame)
