"""
Tests for dags/src/data_ingestion.py.

Covers: cleanup_data_files
Used by the data_ingestion_dag.
"""

import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from pathlib import Path

from src.data_ingestion import cleanup_data_files


class TestCleanupDataFiles:
    @pytest.fixture
    def temp_data_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create sample data files
            (Path(tmpdir) / "data_2020.csv").write_text("a,b,c\n1,2,3")
            (Path(tmpdir) / "data_2020.xls").write_text("fake xls content")
            (Path(tmpdir) / "data_2020.xlsx").write_text("fake xlsx content")
            (Path(tmpdir) / "archive.zip").write_text("zip content")
            # A non-data file that should be left alone
            (Path(tmpdir) / "readme.txt").write_text("keep me")
            yield tmpdir

    def test_cleanup_deletes_csv(self, temp_data_dir):
        cleanup_data_files(temp_data_dir)
        d = Path(temp_data_dir)
        assert not (d / "data_2020.csv").exists()

    def test_cleanup_deletes_xls(self, temp_data_dir):
        cleanup_data_files(temp_data_dir)
        d = Path(temp_data_dir)
        assert not (d / "data_2020.xls").exists()

    def test_cleanup_deletes_xlsx(self, temp_data_dir):
        cleanup_data_files(temp_data_dir)
        d = Path(temp_data_dir)
        assert not (d / "data_2020.xlsx").exists()

    def test_cleanup_deletes_zip(self, temp_data_dir):
        cleanup_data_files(temp_data_dir)
        d = Path(temp_data_dir)
        assert not (d / "archive.zip").exists()

    def test_cleanup_keeps_other_files(self, temp_data_dir):
        cleanup_data_files(temp_data_dir)
        d = Path(temp_data_dir)
        assert (d / "readme.txt").exists()

    def test_cleanup_non_existent_directory_does_not_raise(self):
        # Should not raise when directory doesn't exist
        cleanup_data_files("/tmp/non_existent_dir_12345")

    def test_cleanup_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cleanup_data_files(tmpdir)
            assert Path(tmpdir).exists()
            assert len(list(Path(tmpdir).iterdir())) == 0

    def test_cleanup_reports_deleted_files(self, temp_data_dir, capsys):
        cleanup_data_files(temp_data_dir)
        captured = capsys.readouterr()
        assert "Deleted:" in captured.out
        assert "Cleanup completed:" in captured.out
