import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.ingestion.downloader import download_and_extract
from src.db.ingestion_postgre import ingest_postgres
from src.db.ingestion_features import ingest_features
from src.db.ingestion_weather import ingest_weather

DATA_DIR = "/opt/airflow/dags/src/data_folder"


def run_full_pipeline(start_date="2020-01-01", end_date="2020-12-31", data_dir=DATA_DIR, cleanup=True):
    """
    Run the complete data ingestion pipeline
    
    Args:
        start_date (str): Start date for weather data (default: "2020-01-01")
        end_date (str): End date for weather data (default: "2020-12-31")
        data_dir (str): Directory for data storage (default: "data")
        cleanup (bool): Whether to cleanup temporary files (default: True)
    """
    print("Starting data ingestion pipeline...")
    
    print("Step 1: Downloading and extracting consumption data...")
    extracted_files= download_and_extract(start_year=2012, target_dir=data_dir)
    extracted_files_count = len(extracted_files)
    print(f"Extracted {extracted_files_count} files.")
    for e in extracted_files:
        print(f"Extracted File: {e}")
    print("Step 2: Ingesting consumption data into PostgreSQL...")
    ingest_postgres()
    
    print("Step 3: Ingesting features into PostgreSQL...")
    ingest_features()
    
    print("Step 4: Ingesting weather data into PostgreSQL...")
    ingest_weather(start_date, end_date)
    
    print("Data ingestion pipeline completed successfully!")
    
    if cleanup:
        print("Cleaning up temporary files...")
        for file_path in extracted_files:
            try:
                os.remove(file_path)
                print(f"Removed file: {file_path}")
            except Exception as e:
                print(f"Error removing file {file_path}: {e}")


if __name__ == "__main__":
    run_full_pipeline()